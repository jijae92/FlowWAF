import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
import math
import json
import os
import boto3
from datetime import datetime, timedelta

# Assuming storage.py is in the same directory or accessible via backend.analytics
from backend.analytics import storage

# TODO: Make S3 client and bucket names configurable via environment variables
# For now, using placeholders.
S3_CLIENT = boto3.client('s3')
BASELINE_BUCKET = os.environ.get("BASELINE_BUCKET", "your-baseline-bucket-name")
TRAIN_DAYS = int(os.environ.get("TRAIN_DAYS", "7")) # Number of days for initial training

def ewma(series: pd.Series, alpha: float) -> pd.Series:
    """
    Calculates the Exponentially Weighted Moving Average (EWMA) for a given series.

    Args:
        series (pd.Series): The input data series.
        alpha (float): The smoothing factor, between 0 and 1.
                       Higher alpha discounts older observations faster.

    Returns:
        pd.Series: The EWMA series.
    """
    return series.ewm(alpha=alpha, adjust=False).mean()

def ewma_std(series: pd.Series, alpha: float) -> pd.Series:
    """
    Calculates the Exponentially Weighted Moving Standard Deviation (EWMSD) for a given series.

    Args:
        series (pd.Series): The input data series.
        alpha (float): The smoothing factor, between 0 and 1.

    Returns:
        pd.Series: The EWMSD series.
    """
    # EWM variance is calculated as EWM(x^2) - (EWM(x))^2
    # Then take the square root for standard deviation
    ewm_mean = ewma(series, alpha)
    ewm_var = series.ewm(alpha=alpha, adjust=False).var()
    # Adjust for bias in small samples if needed, but for streaming, this is often ignored.
    return np.sqrt(ewm_var)


def zscore(series: pd.Series, baseline_mean: float, baseline_std: float) -> pd.Series:
    """
    Calculates the Z-score for each point in a series against a given baseline mean and standard deviation.

    Args:
        series (pd.Series): The input data series.
        baseline_mean (float): The mean from the baseline.
        baseline_std (float): The standard deviation from the baseline.

    Returns:
        pd.Series: The Z-score series. Returns 0 if baseline_std is 0 to avoid division by zero.
    """
    if baseline_std == 0:
        # If std is zero, all values are expected to be the mean.
        # Any deviation is an anomaly, but z-score formula breaks.
        # We can return a large z-score for non-mean values, or 0 for mean values.
        # For simplicity, returning 0 for all if std is 0, implying no deviation from a constant baseline.
        # TODO: Revisit this edge case. A better approach might be to flag any non-mean value as anomalous.
        return pd.Series(0.0, index=series.index)
    return (series - baseline_mean) / baseline_std

def get_baseline_key(metric: str, key: str, subkey: str) -> str:
    """Constructs the S3 key for storing baseline data."""
    # Ensure S3 key is valid (e.g., replace '/' in key/subkey if they are part of data)
    # For simplicity, assuming key/subkey are safe for S3 paths.
    # TODO: Sanitize key and subkey to prevent S3 path issues.
    return f"baselines/{metric}/{key}/{subkey}.json"

def load_or_train_baseline(
    s3_client: Any,
    bucket_name: str,
    metric: str,
    key: str,
    subkey: str,
    historical_data: pd.Series,
    alpha: float,
    train_days: int
) -> Tuple[float, float]:
    """
    Loads baseline from S3 or trains a new one if not found or if it's the first run.

    Args:
        s3_client: Boto3 S3 client.
        bucket_name (str): S3 bucket name for baselines.
        metric (str): The metric name (e.g., 'request_count').
        key (str): The primary identifier (e.g., IP address).
        subkey (str): The secondary identifier (e.g., URI).
        historical_data (pd.Series): Historical data for training if baseline is new.
        alpha (float): EWMA smoothing factor.
        train_days (int): Number of days to consider for initial training.

    Returns:
        Tuple[float, float]: (baseline_mean, baseline_std)
    """
    baseline_s3_key = get_baseline_key(metric, key, subkey)
    baseline_data = storage.get_baseline(s3_client, bucket_name, baseline_s3_key)

    if baseline_data:
        # TODO: Add logic to check if baseline is stale and needs retraining
        return baseline_data['mean'], baseline_data['std']
    else:
        print(f"No baseline found for {metric}/{key}/{subkey}. Training new baseline...")
        if historical_data.empty or len(historical_data) < 2: # Need at least 2 points for std dev
            # If not enough historical data, initialize with current value or a default.
            # This is a cold start scenario.
            initial_mean = historical_data.iloc[-1] if not historical_data.empty else 0.0
            initial_std = 0.0 # Cannot calculate std with less than 2 points
            print(f"Insufficient historical data for training. Initializing with mean={initial_mean}, std={initial_std}")
        else:
            # Train EWMA and EWMSD on historical data
            trained_mean = ewma(historical_data, alpha).iloc[-1]
            trained_std = ewma_std(historical_data, alpha).iloc[-1]
            initial_mean = trained_mean
            initial_std = trained_std

        # Save the newly trained baseline
        storage.put_baseline(s3_client, bucket_name, baseline_s3_key, {'mean': initial_mean, 'std': initial_std})
        return initial_mean, initial_std


def detect_anomalies(
    data_points: List[Dict[str, Any]],
    s3_client: Any,
    baseline_bucket: str,
    alpha: float,
    sigma: float,
    min_count: int,
    topk: int,
    train_days: int
) -> List[Dict[str, Any]]:
    """
    Detects anomalies in data points using EWMA and 3-sigma rule.

    Args:
        data_points (List[Dict[str, Any]]): List of data points.
                                            Each dict should have 'minute', 'key', 'subkey', 'value', 'metric'.
        s3_client: Boto3 S3 client.
        baseline_bucket (str): S3 bucket name for baselines.
        alpha (float): EWMA smoothing factor.
        sigma (float): Number of standard deviations from the mean to trigger an anomaly.
        min_count (int): Minimum number of data points required to calculate EWMA/EWMSD.
                         (Currently not fully utilized, but good for future enhancements).
        topk (int): Number of top anomalies to return.
        train_days (int): Number of days to consider for initial baseline training.

    Returns:
        List[Dict[str, Any]]: A list of detected anomalies, each with details.
                              Sorted by absolute z-score (score) in descending order.
    """
    if not data_points:
        return []

    # Group data by metric, key, subkey
    grouped_data = {}
    for dp in data_points:
        metric = dp['metric']
        key = dp['key']
        subkey = dp.get('subkey', 'N/A') # subkey might be optional
        group_key = (metric, key, subkey)
        if group_key not in grouped_data:
            grouped_data[group_key] = []
        grouped_data[group_key].append(dp)

    anomalies = []

    for (metric, key, subkey), group in grouped_data.items():
        # Sort by minute to ensure correct EWMA calculation
        group.sort(key=lambda x: x['minute'])
        
        # Convert to pandas Series for EWMA calculation
        # TODO: Fetch actual historical data for training, not just current group
        # For now, we'll use the current group as "historical" for baseline training if needed.
        values = pd.Series([d['value'] for d in group], index=[d['minute'] for d in group])

        if values.empty:
            continue

        # Load or train baseline for this specific metric/key/subkey combination
        baseline_mean, baseline_std = load_or_train_baseline(
            s3_client, baseline_bucket, metric, key, subkey, values, alpha, train_days
        )

        # Calculate EWMA and EWMSD for the current data point
        current_value = values.iloc[-1]
        
        # Update baseline with current value for next iteration
        # This is a simplified update. A more robust system would update the baseline
        # with the EWMA of the current value and then save it.
        updated_mean = (1 - alpha) * baseline_mean + alpha * current_value
        updated_std = math.sqrt((1 - alpha) * (baseline_std**2) + alpha * ((current_value - updated_mean)**2))
        
        # Handle edge case where std is 0
        if updated_std < 1e-6: # Effectively zero
            updated_std = 1e-6 # Prevent division by zero, treat as very small deviation

        # Calculate Z-score for the current value
        score = (current_value - updated_mean) / updated_std

        # Check for anomaly
        if abs(score) > sigma:
            anomalies.append({
                "key": key,
                "subkey": subkey,
                "minute": group[-1]['minute'],
                "value": current_value,
                "score": score,
                "baseline_mean": updated_mean,
                "baseline_std": updated_std,
                "metric": metric,
                "mode": "high" if score > 0 else "low"
            })
        
        # Save updated baseline
        storage.put_baseline(s3_client, baseline_bucket, get_baseline_key(metric, key, subkey), {
            'mean': updated_mean,
            'std': updated_std,
            'last_updated': datetime.utcnow().isoformat()
        })

    # Sort anomalies by absolute score and return top-k
    anomalies.sort(key=lambda x: abs(x['score']), reverse=True)
    return anomalies[:topk]

# Example Usage / Edge Case TODOs:
if __name__ == '__main__':
    # --- Example 1: Basic Anomaly Detection ---
    print("--- Example 1: Basic Anomaly Detection ---")
    # Simulate data points over time for a single metric/key/subkey
    sample_data = [
        {'minute': '2023-10-26T10:00', 'key': '1.1.1.1', 'subkey': '/pathA', 'value': 10, 'metric': 'requests'},
        {'minute': '2023-10-26T10:01', 'key': '1.1.1.1', 'subkey': '/pathA', 'value': 12, 'metric': 'requests'},
        {'minute': '2023-10-26T10:02', 'key': '1.1.1.1', 'subkey': '/pathA', 'value': 11, 'metric': 'requests'},
        {'minute': '2023-10-26T10:03', 'key': '1.1.1.1', 'subkey': '/pathA', 'value': 100, 'metric': 'requests'}, # Anomaly
        {'minute': '2023-10-26T10:04', 'key': '1.1.1.1', 'subkey': '/pathA', 'value': 15, 'metric': 'requests'},
    ]

    # Mock S3 client for example
    class MockS3Client:
        def __init__(self):
            self.store = {}
        def get_object(self, Bucket, Key):
            if Key in self.store:
                return {'Body': type('obj', (object,), {'read': lambda: self.store[Key].encode('utf-8')})()}
            raise S3_CLIENT.exceptions.NoSuchKey({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
        def put_object(self, Bucket, Key, Body, ContentType):
            self.store[Key] = Body

    mock_s3_client = MockS3Client()
    # Set environment variables for the example
    os.environ["BASELINE_BUCKET"] = "mock-baseline-bucket"
    os.environ["TRAIN_DAYS"] = "1" # Use 1 day for training in example

    anomalies_found = detect_anomalies(
        sample_data,
        mock_s3_client,
        os.environ["BASELINE_BUCKET"],
        alpha=0.3,
        sigma=3.0,
        min_count=2,
        topk=5,
        train_days=int(os.environ["TRAIN_DAYS"])
    )
    print(f"Anomalies detected: {json.dumps(anomalies_found, indent=2)}")

    # --- Example 2: Cold Start Scenario ---
    print("\n--- Example 2: Cold Start Scenario ---")
    cold_start_data = [
        {'minute': '2023-10-26T11:00', 'key': '2.2.2.2', 'subkey': '/new_path', 'value': 50, 'metric': 'requests'},
    ]
    anomalies_cold_start = detect_anomalies(
        cold_start_data,
        mock_s3_client,
        os.environ["BASELINE_BUCKET"],
        alpha=0.3,
        sigma=3.0,
        min_count=2,
        topk=5,
        train_days=int(os.environ["TRAIN_DAYS"])
    )
    print(f"Anomalies detected (cold start): {json.dumps(anomalies_cold_start, indent=2)}")

    # --- TODO: Edge Cases ---
    # TODO: Test with all values being constant (std dev = 0)
    # TODO: Test with very sparse data (e.g., only one data point)
    # TODO: Test with different alpha and sigma values
    # TODO: Test with multiple metrics/keys/subkeys in a single run
    # TODO: Implement proper historical data fetching for baseline training
    # TODO: Implement baseline decay/aging for features that are no longer active