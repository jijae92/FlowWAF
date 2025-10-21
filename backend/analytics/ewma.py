import pandas as pd

# TODO:
# - This is a simplified implementation. A robust version would need to handle:
#   - Cold starts (first time a feature is seen).
#   - Decay of old, unseen features from the baseline.
#   - Different weights (alpha) for different metrics.

class EWMA:
    """
    Exponentially Weighted Moving Average for statistical anomaly detection.
    """
    def __init__(self, alpha=0.3, threshold=3.0):
        """
        Args:
            alpha (float): The smoothing factor, between 0 and 1.
                           Higher alpha discounts older observations faster.
            threshold (float): The number of standard deviations from the mean
                               to consider a data point an anomaly (3-sigma rule).
        """
        self.alpha = alpha
        self.threshold = threshold
        self.baseline = {} # Stores {'feature_key': {'mean': val, 'std': val}}

    def update_baseline(self, new_data: pd.DataFrame):
        """
        Updates the baseline with new data.
        `new_data` is a DataFrame with feature keys as index and metrics as columns.
        """
        # TODO: Implement the logic to update self.baseline
        # For each feature in new_data:
        # 1. If feature is new, initialize its mean and std.
        # 2. If feature exists, update its EWMA and EW-StdDev.
        pass

    def find_anomalies(self, current_data: pd.DataFrame) -> list:
        """
        Compares current data against the baseline to find anomalies.
        
        Args:
            current_data: A DataFrame of the latest metrics, indexed by feature key.

        Returns:
            A list of dictionaries, where each dictionary describes an anomaly.
        """
        anomalies = []
        # TODO: Implement the core detection logic.
        # For each feature in current_data:
        # 1. Get the baseline mean and std for that feature.
        # 2. Calculate the z-score (sigma).
        # 3. If z-score > self.threshold, it's an anomaly.
        # 4. Append the anomaly details to the `anomalies` list.
        
        # Example dummy logic:
        for index, row in current_data.iterrows():
            # Pretend we found an anomaly
            if row['request_count'] > 1000:
                anomaly = {
                    "feature_key": index,
                    "metric": "request_count",
                    "value": row['request_count'],
                    "sigma": 99.0 # Dummy sigma
                }
                anomalies.append(anomaly)

        return anomalies
