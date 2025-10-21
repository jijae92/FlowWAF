import json
import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any, Optional
import hashlib
from datetime import datetime

def _generate_s3_key(metric: str, key: str, subkey: str) -> str:
    """
    Generates a unique S3 key for baseline storage using SHA1 hashes of key and subkey.
    This helps in handling special characters and long names in S3 paths.
    """
    # TODO: Consider a more robust way to handle very long keys/subkeys if SHA1 hash collisions are a concern
    # For most use cases, SHA1 should be sufficient for uniqueness in S3 paths.
    hashed_key = hashlib.sha1(key.encode('utf-8')).hexdigest()
    hashed_subkey = hashlib.sha1(subkey.encode('utf-8')).hexdigest()
    return f"baselines/{metric}/{hashed_key}/{hashed_subkey}.json"

def get_baseline(s3_client: Any, bucket_name: str, s3_key: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves baseline data from an S3 object.

    Args:
        s3_client: Boto3 S3 client.
        bucket_name (str): The name of the S3 bucket where baselines are stored.
        s3_key (str): The S3 key (full path) to the baseline JSON file.

    Returns:
        Optional[Dict[str, Any]]: The baseline data as a dictionary if found, otherwise None.
    """
    print(f"Attempting to load baseline from s3://{bucket_name}/{s3_key}")
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        baseline_content = response['Body'].read().decode('utf-8')
        return json.loads(baseline_content)
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print(f"Baseline file not found at s3://{bucket_name}/{s3_key}.")
            return None
        else:
            print(f"Error loading baseline from S3 ({s3_key}): {e}")
            # TODO: Add more specific error handling or retry logic
            raise
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from baseline file {s3_key}: {e}")
        # TODO: Consider data corruption, perhaps move to a dead-letter S3 prefix
        return None

def put_baseline(s3_client: Any, bucket_name: str, s3_key: str, baseline_data: Dict[str, Any]):
    """
    Stores baseline data as a JSON object in S3.

    Args:
        s3_client: Boto3 S3 client.
        bucket_name (str): The name of the S3 bucket where baselines are stored.
        s3_key (str): The S3 key (full path) to store the baseline JSON file.
        baseline_data (Dict[str, Any]): The baseline data to store.
    """
    print(f"Attempting to save baseline to s3://{bucket_name}/{s3_key}")
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json.dumps(baseline_data, indent=2),
            ContentType='application/json'
        )
        print(f"Successfully saved baseline to s3://{bucket_name}/{s3_key}")
    except ClientError as e:
        print(f"Error saving baseline to S3 ({s3_key}): {e}")
        # TODO: Add more specific error handling or retry logic
        raise

# Example Usage:
if __name__ == '__main__':
    # Mock S3 client for example
    class MockS3Client:
        def __init__(self):
            self.store = {}
            self.exceptions = type('obj', (object,), {'NoSuchKey': ClientError}) # Mock NoSuchKey
        def get_object(self, Bucket, Key):
            if Key in self.store:
                return {'Body': type('obj', (object,), {'read': lambda: self.store[Key].encode('utf-8')})()}
            raise self.exceptions.NoSuchKey({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
        def put_object(self, Bucket, Key, Body, ContentType):
            self.store[Key] = Body
            print(f"Mock S3: Stored {Key} in {Bucket}")

    mock_s3_client = MockS3Client()
    test_bucket = "test-baseline-bucket"

    # Test data
    test_metric = "requests"
    test_key = "192.168.1.100"
    test_subkey = "/api/v1/data"
    test_baseline = {"mean": 100.5, "std": 10.2, "last_updated": datetime.utcnow().isoformat()}

    # Generate S3 key
    generated_s3_key = _generate_s3_key(test_metric, test_key, test_subkey)
    print(f"Generated S3 Key: {generated_s3_key}")

    # 1. Test get_baseline (not found)
    print("\n--- Test 1: Get baseline (not found) ---")
    retrieved_baseline = get_baseline(mock_s3_client, test_bucket, generated_s3_key)
    print(f"Retrieved: {retrieved_baseline}")
    assert retrieved_baseline is None

    # 2. Test put_baseline
    print("\n--- Test 2: Put baseline ---")
    put_baseline(mock_s3_client, test_bucket, generated_s3_key, test_baseline)

    # 3. Test get_baseline (found)
    print("\n--- Test 3: Get baseline (found) ---")
    retrieved_baseline = get_baseline(mock_s3_client, test_bucket, generated_s3_key)
    print(f"Retrieved: {retrieved_baseline}")
    assert retrieved_baseline == test_baseline

    # 4. Test put_baseline (update)
    print("\n--- Test 4: Put baseline (update) ---")
    updated_baseline = {"mean": 105.0, "std": 11.0, "last_updated": datetime.utcnow().isoformat()}
    put_baseline(mock_s3_client, test_bucket, generated_s3_key, updated_baseline)
    retrieved_baseline = get_baseline(mock_s3_client, test_bucket, generated_s3_key)
    print(f"Retrieved after update: {retrieved_baseline}")
    assert retrieved_baseline == updated_baseline

    print("\nAll storage tests passed (mocked S3).")