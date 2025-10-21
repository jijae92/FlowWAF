import unittest
import pandas as pd
import numpy as np
from backend.analytics.ewma import ewma, ewma_std, zscore, detect_anomalies, get_baseline_key
from unittest.mock import MagicMock, patch
import os
import json
from datetime import datetime, timedelta

class TestEWMA(unittest.TestCase):

    def setUp(self):
        self.alpha = 0.3
        self.sigma = 3.0
        self.min_count = 2
        self.topk = 5
        self.train_days = 1 # For testing purposes

        # Mock S3 client for baseline storage
        self.mock_s3_client = MagicMock()
        self.mock_s3_client.exceptions.NoSuchKey = type('obj', (object,), {'__init__': lambda self, *args, **kwargs: None}) # Mock NoSuchKey exception
        self.mock_s3_client.get_object.side_effect = self._mock_get_object
        self.mock_s3_client.put_object.side_effect = self._mock_put_object
        self.baseline_store = {} # In-memory store for baselines

        os.environ["BASELINE_BUCKET"] = "mock-baseline-bucket"
        os.environ["TRAIN_DAYS"] = str(self.train_days)
        os.environ["EWMA_ALPHA"] = str(self.alpha)
        os.environ["SIGMA"] = str(self.sigma)
        os.environ["TOP_K"] = str(self.topk)

    def _mock_get_object(self, Bucket, Key):
        if Key in self.baseline_store:
            return {'Body': type('obj', (object,), {'read': lambda: self.baseline_store[Key].encode('utf-8')})()}
        raise self.mock_s3_client.exceptions.NoSuchKey({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')

    def _mock_put_object(self, Bucket, Key, Body, ContentType):
        self.baseline_store[Key] = Body

    def test_ewma_calculation(self):
        """Test basic EWMA calculation."""
        data = pd.Series([10, 12, 11, 13, 15])
        expected_ewma = pd.Series([10.0, 10.6, 10.82, 11.574, 12.5018]) # Calculated manually with alpha=0.3
        result = ewma(data, self.alpha)
        pd.testing.assert_series_equal(result, expected_ewma, check_exact=False, rtol=1e-2)

    def test_ewma_std_calculation(self):
        """Test basic EWMA standard deviation calculation."""
        data = pd.Series([10, 12, 11, 13, 15])
        # Expected values are harder to calculate manually, so we'll check for non-zero and reasonable values
        result = ewma_std(data, self.alpha)
        self.assertFalse(result.isnull().any())
        self.assertTrue((result >= 0).all())
        self.assertGreater(result.iloc[-1], 0) # Should have a positive std dev

    def test_zscore_calculation(self):
        """Test z-score calculation."""
        series = pd.Series([10, 15, 20])
        baseline_mean = 15.0
        baseline_std = 2.0
        expected_zscore = pd.Series([-2.5, 0.0, 2.5])
        result = zscore(series, baseline_mean, baseline_std)
        pd.testing.assert_series_equal(result, expected_zscore, check_exact=False, rtol=1e-2)

        # Test with zero standard deviation
        result_zero_std = zscore(pd.Series([10, 10, 10]), 10.0, 0.0)
        pd.testing.assert_series_equal(result_zero_std, pd.Series([0.0, 0.0, 0.0]))

    def test_detect_anomalies_burst(self):
        """
        Test anomaly detection with a synthetic burst in time series data.
        """
        # Generate synthetic data with a burst
        base_value = 10
        burst_value = 100
        data_points = []
        for i in range(10):
            minute = (datetime(2023, 1, 1, 10, 0) + timedelta(minutes=i)).isoformat()
            value = base_value + np.random.normal(0, 1) # Normal fluctuations
            if i == 7: # Introduce a burst
                value = burst_value + np.random.normal(0, 5)
            data_points.append({
                'minute': minute,
                'key': 'test_ip',
                'subkey': 'test_uri',
                'value': value,
                'metric': 'requests'
            })
        
        # Run anomaly detection
        anomalies = detect_anomalies(
            data_points,
            self.mock_s3_client,
            os.environ["BASELINE_BUCKET"],
            alpha=self.alpha,
            sigma=self.sigma,
            min_count=self.min_count,
            topk=self.topk,
            train_days=self.train_days
        )

        self.assertGreater(len(anomalies), 0, "Should detect at least one anomaly during burst.")
        # Check if the anomaly is the burst point and has a high score
        burst_anomaly = next((a for a in anomalies if a['value'] > base_value * 5), None)
        self.assertIsNotNone(burst_anomaly, "Burst anomaly should be present.")
        self.assertGreater(abs(burst_anomaly['score']), self.sigma, "Anomaly score should be greater than sigma.")
        self.assertEqual(burst_anomaly['mode'], 'high', "Anomaly mode should be 'high'.")

    def test_detect_anomalies_no_anomaly(self):
        """Test anomaly detection with normal data, expecting no anomalies."""
        data_points = []
        for i in range(10):
            minute = (datetime(2023, 1, 1, 10, 0) + timedelta(minutes=i)).isoformat()
            value = 10 + np.random.normal(0, 0.5) # Small fluctuations
            data_points.append({
                'minute': minute,
                'key': 'test_ip_normal',
                'subkey': 'test_uri_normal',
                'value': value,
                'metric': 'requests'
            })
        
        anomalies = detect_anomalies(
            data_points,
            self.mock_s3_client,
            os.environ["BASELINE_BUCKET"],
            alpha=self.alpha,
            sigma=self.sigma,
            min_count=self.min_count,
            topk=self.topk,
            train_days=self.train_days
        )
        self.assertEqual(len(anomalies), 0, "Should detect no anomalies for normal data.")

    def test_detect_anomalies_cold_start(self):
        """Test anomaly detection with cold start (no prior baseline)."""
        # Clear baseline store for cold start
        self.baseline_store = {}
        
        cold_start_data = [
            {'minute': '2023-01-01T11:00', 'key': 'new_ip', 'subkey': 'new_uri', 'value': 50, 'metric': 'requests'},
            {'minute': '2023-01-01T11:01', 'key': 'new_ip', 'subkey': 'new_uri', 'value': 55, 'metric': 'requests'},
            {'minute': '2023-01-01T11:02', 'key': 'new_ip', 'subkey': 'new_uri', 'value': 150, 'metric': 'requests'}, # Anomaly
        ]

        anomalies = detect_anomalies(
            cold_start_data,
            self.mock_s3_client,
            os.environ["BASELINE_BUCKET"],
            alpha=self.alpha,
            sigma=self.sigma,
            min_count=self.min_count,
            topk=self.topk,
            train_days=self.train_days
        )
        self.assertGreater(len(anomalies), 0, "Should detect anomaly even with cold start if deviation is high.")
        self.assertGreater(abs(anomalies[0]['score']), self.sigma)

    def test_detect_anomalies_multiple_metrics(self):
        """Test detection with multiple metrics/keys/subkeys."""
        data_points = [
            {'minute': '2023-01-01T12:00', 'key': 'ip1', 'subkey': 'uri1', 'value': 10, 'metric': 'requests'},
            {'minute': '2023-01-01T12:01', 'key': 'ip1', 'subkey': 'uri1', 'value': 12, 'metric': 'requests'},
            {'minute': '2023-01-01T12:02', 'key': 'ip1', 'subkey': 'uri1', 'value': 100, 'metric': 'requests'}, # Anomaly 1
            {'minute': '2023-01-01T12:00', 'key': 'ip2', 'subkey': 'uri2', 'value': 5, 'metric': 'connections'},
            {'minute': '2023-01-01T12:01', 'key': 'ip2', 'subkey': 'uri2', 'value': 6, 'metric': 'connections'},
            {'minute': '2023-01-01T12:02', 'key': 'ip2', 'subkey': 'uri2', 'value': 50, 'metric': 'connections'}, # Anomaly 2
        ]
        anomalies = detect_anomalies(
            data_points,
            self.mock_s3_client,
            os.environ["BASELINE_BUCKET"],
            alpha=self.alpha,
            sigma=self.sigma,
            min_count=self.min_count,
            topk=self.topk,
            train_days=self.train_days
        )
        self.assertEqual(len(anomalies), 2, "Should detect two anomalies for different metrics/keys.")
        self.assertIn('requests', [a['metric'] for a in anomalies])
        self.assertIn('connections', [a['metric'] for a in anomalies])

if __name__ == '__main__':
    unittest.main()