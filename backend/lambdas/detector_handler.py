import os
import json
import boto3
import time
from backend.analytics import ewma, aggregators, ioc, notifier, storage, config

# TODO:
# - Implement the full workflow:
#   1. Check if event is a warmup call and exit early if so.
#   2. Read SQL queries from the `sql/queries` directory.
#   3. Execute Athena queries using a helper function.
#   4. Fetch results from S3.
#   5. Process results with `aggregators.py`.
#   6. Load baseline from `storage.py`.
#   7. Run `ewma.py` to find statistical anomalies.
#   8. For anomalies, use `ioc.py` to check for known bad indicators.
#   9. If anomalies or IOC matches are found, format a message.
#   10. Use `notifier.py` to send the message to SNS.
#   11. Update the baseline with `storage.py`.

print("Loading function")

# Initialize clients and config outside the handler for reuse
ATHENA_CLIENT = boto3.client("athena")
SNS_CLIENT = boto3.client("sns")
S3_CLIENT = boto3.client("s3")

# Load configuration from environment variables
APP_CONFIG = config.get_config()

def run_athena_query(query_string):
    """Helper function to run query and return execution ID."""
    # TODO: Implement robust query execution and waiting logic.
    print(f"Running query: {query_string[:200]}...")
    response = ATHENA_CLIENT.start_query_execution(
        QueryString=query_string,
        QueryExecutionContext={"Database": APP_CONFIG.athena_database},
        ResultConfiguration={"OutputLocation": APP_CONFIG.athena_output_location},
        WorkGroup=APP_CONFIG.athena_workgroup,
    )
    return response["QueryExecutionId"]

def handler(event, context):
    """
    Main handler for anomaly detection.
    Triggered by EventBridge schedule.
    """
    print(f"Received event: {json.dumps(event)}")

    # Handle optional warmup pings
    if event.get("source") == "lambda.warmer":
        print("Warmup call received. Exiting.")
        return {"statusCode": 200, "body": "Warmed up!"}

    # --- Main Logic ---
    print("Starting anomaly detection cycle.")

    # 1. Read SQL query
    # TODO: Read from `backend/sql/queries/union_hotspots.sql`
    query = "SELECT 1;" # Placeholder

    # 2. Run Athena query
    # execution_id = run_athena_query(query)
    # TODO: Wait for query to complete

    # 3. Get results
    # TODO: Fetch results from S3 output location

    # 4. Analyze results
    # hotspots = aggregators.vectorize_features(athena_results)
    # baseline = storage.load_baseline(S3_CLIENT, APP_CONFIG.baseline_bucket, ...)
    # anomalies = ewma.find_anomalies(hotspots, baseline)
    # ioc_matches = ioc.find_matches(hotspots)

    anomalies = [{"ip": "1.2.3.4", "metric": "requests", "value": 500, "sigma": 4.5}] # Dummy data
    ioc_matches = [] # Dummy data

    # 5. Notify if necessary
    if anomalies or ioc_matches:
        print("Anomalies or IOC matches found. Sending notification.")
        message = notifier.format_message(anomalies, ioc_matches)
        notifier.send_sns_notification(SNS_CLIENT, APP_CONFIG.sns_topic_arn, message)
    else:
        print("No anomalies detected.")

    # 6. Update baseline
    # TODO: storage.save_baseline(...)
    print("Detection cycle complete.")

    return {
        "statusCode": 200,
        "body": json.dumps("Detection cycle finished successfully."),
    }
