import unittest
import pandas as pd
from backend.analytics.aggregators import vectorize_features # Assuming this function exists

class TestAggregators(unittest.TestCase):

    def test_vectorize_features_waf_data(self):
        """
        Test feature vectorization for sample WAF Athena results.
        Assumes 'union_hotspots.sql' output format.
        """
        # Sample Athena result DataFrame (simulating union_hotspots.sql output)
        data = {
            'minute': ['2023-10-26T10:00', '2023-10-26T10:00', '2023-10-26T10:00'],
            'key': ['1.1.1.1', '2.2.2.2', '1.1.1.1'],
            'subkey': ['/pathA', '/pathB', '/pathC'],
            'country': ['US', 'US', 'JP'],
            'rule_label': [None, None, 'SQLI'],
            'value': [100, 50, 120],
            'metric': ['request_count', 'request_count', 'request_count'],
            'source_type': ['WAF', 'WAF', 'WAF']
        }
        df = pd.DataFrame(data)

        # The current vectorize_features in aggregators.py is a placeholder.
        # It should ideally transform this into a format suitable for EWMA.
        # For now, we'll test its basic functionality.
        result_df = vectorize_features(df)

        self.assertIsInstance(result_df, pd.DataFrame)
        self.assertFalse(result_df.empty)
        self.assertIn('feature_key', result_df.index.name) # Check if index is set
        self.assertEqual(len(result_df), 3) # Expect 3 unique feature keys

        # Check if values are correctly transferred
        self.assertIn(100, result_df['value'].values)
        self.assertIn(50, result_df['value'].values)
        self.assertIn(120, result_df['value'].values)

    def test_vectorize_features_vpc_data(self):
        """
        Test feature vectorization for sample VPC Flow Athena results.
        Assumes 'union_hotspots.sql' output format.
        """
        data = {
            'minute': ['2023-10-26T10:00', '2023-10-26T10:00'],
            'key': ['172.31.0.1', '172.31.0.2'],
            'subkey': ['80', '443'],
            'country': [None, None],
            'rule_label': [None, None],
            'value': [200, 300],
            'metric': ['connection_count', 'connection_count'],
            'source_type': ['VPC', 'VPC']
        }
        df = pd.DataFrame(data)

        result_df = vectorize_features(df)

        self.assertIsInstance(result_df, pd.DataFrame)
        self.assertFalse(result_df.empty)
        self.assertIn('feature_key', result_df.index.name)
        self.assertEqual(len(result_df), 2)

    def test_vectorize_features_empty_input(self):
        """Test with an empty DataFrame input."""
        df = pd.DataFrame()
        result_df = vectorize_features(df)
        self.assertIsInstance(result_df, pd.DataFrame)
        self.assertTrue(result_df.empty)

if __name__ == '__main__':
    unittest.main()