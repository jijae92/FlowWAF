import json
import boto3
from botocore.exceptions import ClientError

# TODO:
# - Implement loading and saving of the EWMA baseline state.
# - The baseline should contain the moving averages and standard deviations for each feature vector.
# - Consider using DynamoDB as an alternative for more granular state management,
#   though S3 is simpler and cheaper for this use case.

BASELINE_KEY = "dos-detection/baseline.json"

def load_baseline(s3_client, bucket_name: str) -> dict:
    """
    Loads the baseline statistics from an S3 object.
    Returns an empty dictionary if the baseline file doesn't exist.
    """
    print(f"Loading baseline from s3://{bucket_name}/{BASELINE_KEY}")
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=BASELINE_KEY)
        baseline_content = response['Body'].read().decode('utf-8')
        return json.loads(baseline_content)
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print("Baseline file not found. Starting with a fresh baseline.")
            return {}
        else:
            print(f"Error loading baseline from S3: {e}")
            raise

def save_baseline(s3_client, bucket_name: str, baseline_data: dict):
    """
    Saves the updated baseline statistics to an S3 object.
    """
    print(f"Saving baseline to s3://{bucket_name}/{BASELINE_KEY}")
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=BASELINE_KEY,
            Body=json.dumps(baseline_data, indent=2),
            ContentType='application/json'
        )
    except ClientError as e:
        print(f"Error saving baseline to S3: {e}")
        raise
