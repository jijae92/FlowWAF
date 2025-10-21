import os
import json
import boto3
import time
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Import analytics modules
from backend.analytics import ewma, aggregators, ioc, notifier, storage, config

# Initialize clients outside the handler for reuse
ATHENA_CLIENT = boto3.client("athena")
S3_CLIENT = boto3.client("s3")
# SNS_CLIENT is initialized within notifier.py, but we might need it here for error notifications
# For now, we'll rely on notifier.py to handle SNS publishing.

# Load configuration from environment variables
APP_CONFIG = config.get_config()

# Initialize IOCMatcher once
IOC_MATCHER = None
try:
    IOC_MATCHER = ioc.load_ioc(path="config/ioc.yml")
except Exception as e:
    print(f"WARNING: Could not load IOC configuration: {e}. IOC matching will be skipped.")

def _read_sql_query(file_path: str) -> str:
    """Reads an SQL query from a file."""
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: SQL query file not found at {file_path}")
        raise

def execute_athena_query(query_string: str, database: str, workgroup: str, output_location: str) -> pd.DataFrame:
    """
    Executes an Athena query, waits for completion, and fetches results into a Pandas DataFrame.
    """
    print(f"Executing Athena query in database '{database}', workgroup '{workgroup}'...")
    print(f"Query (first 200 chars): {query_string[:200]}...")

    try:
        response = ATHENA_CLIENT.start_query_execution(
            QueryString=query_string,
            QueryExecutionContext={'Database': database},
            ResultConfiguration={'OutputLocation': output_location},
            WorkGroup=workgroup
        )
        query_execution_id = response['QueryExecutionId']
        print(f"Query Execution ID: {query_execution_id}")

        # Polling for query completion
        state = 'RUNNING'
        max_retries = 30 # Max 5 minutes (30 * 10s)
        retries = 0
        while state in ['RUNNING', 'QUEUED'] and retries < max_retries:
            time.sleep(10) # Wait for 10 seconds
            query_status = ATHENA_CLIENT.get_query_execution(QueryExecutionId=query_execution_id)
            state = query_status['QueryExecution']['Status']['State']
            print(f"Query status: {state}")
            retries += 1

        if state == 'SUCCEEDED':
            # Fetch results
            results_paginator = ATHENA_CLIENT.get_paginator('get_query_results')
            results_iterator = results_paginator.paginate(QueryExecutionId=query_execution_id)

            rows = []
            column_names = []
            for page in results_iterator:
                if not column_names and 'ResultSet' in page and 'ResultSetMetadata' in page['ResultSet']:
                    column_names = [col['Name'] for col in page['ResultSet']['ResultSetMetadata']['ColumnInfo']]
                
                for row_data in page['ResultSet']['Rows']:
                    # Skip the header row if it's present in the data
                    if row_data == page['ResultSet']['Rows'][0] and len(rows) == 0:
                        continue
                    rows.append([d.get('VarCharValue') for d in row_data['Data']])
            
            if not column_names:
                print("No column names found in Athena query results.")
                return pd.DataFrame()

            df = pd.DataFrame(rows, columns=column_names)
            print(f"Successfully fetched {len(df)} rows from Athena.")
            return df
        else:
            failure_reason = query_status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown reason')
            print(f"Athena query failed or was cancelled. State: {state}, Reason: {failure_reason}")
            # TODO: Implement backoff and retry for transient Athena errors
            raise Exception(f"Athena query failed: {failure_reason}")

    except Exception as e:
        print(f"Error executing Athena query: {e}")
        raise

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
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
    
    # Context for notifications and metrics
    detection_context = {
        "timestamp": datetime.utcnow().isoformat(),
        "source": "DetectorFunction",
        "lambda_request_id": context.aws_request_id,
        "lookback_minutes": APP_CONFIG.lookback_minutes
    }

    try:
        # 1. Prepare SQL queries with dynamic parameters
        # TODO: Use a more robust templating engine if SQL queries become complex
        # For now, simple string replacement.
        sql_params = {
            "database_name": APP_CONFIG.athena_database,
            "LOOKBACK_MINUTES": str(APP_CONFIG.lookback_minutes),
            "TOP_K": str(APP_CONFIG.top_k),
            "log_bucket_name": APP_CONFIG.baseline_bucket # Assuming log_bucket_name is same as baseline_bucket for now
        }

        # Read and substitute parameters in union_hotspots.sql
        union_hotspots_query_template = _read_sql_query("backend/sql/queries/union_hotspots.sql")
        union_hotspots_query = union_hotspots_query_template
        for param, value in sql_params.items():
            union_hotspots_query = union_hotspots_query.replace(f"${{{param}}}", value)
        
        # 2. Execute Athena query to get aggregated hotspots
        hotspots_df = execute_athena_query(
            union_hotspots_query,
            APP_CONFIG.athena_database,
            APP_CONFIG.athena_workgroup,
            APP_CONFIG.athena_output_location
        )

        if hotspots_df.empty:
            print("No hotspot data returned from Athena. Exiting.")
            return {"statusCode": 200, "body": "No data to process."}

        # Convert relevant columns to numeric if they are objects (e.g., 'value')
        for col in ['value']:
            if col in hotspots_df.columns:
                hotspots_df[col] = pd.to_numeric(hotspots_df[col], errors='coerce').fillna(0)

        # Convert DataFrame rows to list of dicts for EWMA processing
        data_points_for_ewma = hotspots_df.to_dict(orient='records')

        # 3. Detect anomalies
        anomalies = ewma.detect_anomalies(
            data_points_for_ewma,
            S3_CLIENT,
            APP_CONFIG.baseline_bucket,
            APP_CONFIG.ewma_alpha,
            APP_CONFIG.sigma,
            min_count=2, # TODO: Make configurable
            topk=APP_CONFIG.top_k,
            train_days=APP_CONFIG.train_days
        )
        print(f"Detected {len(anomalies)} anomalies.")

        # 4. Tag anomalies with IOC matches
        if IOC_MATCHER:
            for anomaly in anomalies:
                record_for_ioc = {
                    'client_ip': anomaly.get('key'), # Assuming 'key' is IP for WAF/VPC
                    'country': anomaly.get('country'), # WAF specific
                    'user_agent': anomaly.get('ua'), # WAF specific
                    'uri': anomaly.get('subkey') # WAF specific
                }
                ioc_result = IOC_MATCHER.match(record_for_ioc)
                if ioc_result['matched']:
                    anomaly['ioc_matches'] = ioc_result['rules']
                    print(f"Anomaly for {anomaly['key']} tagged with IOCs: {ioc_result['rules']}")
        else:
            print("IOCMatcher not initialized. Skipping IOC tagging.")

        # 5. Notify if anomalies are found
        if anomalies:
            print("Anomalies found. Sending notifications.")
            # SNS Notification
            notifier.publish_sns(APP_CONFIG.sns_topic_arn, anomalies, detection_context)

            # Slack Notification (if configured)
            if APP_CONFIG.slack_webhook_url:
                notifier.send_slack_notification(APP_CONFIG.slack_webhook_url, anomalies, detection_context)
            
            # CloudWatch EMF Metrics
            emf_dimensions = {
                "Detector": "FlowWAF",
                "MetricType": "Anomaly",
                "Source": "DetectorFunction"
            }
            emf_metrics = {
                "AnomalyCount": len(anomalies),
                "MaxAnomalyScore": max(abs(f['score']) for f in anomalies) if anomalies else 0
            }
            notifier.emit_emf("FlowWAFSentinel", emf_dimensions, emf_metrics)
        else:
            print("No anomalies detected.")

        print("Detection cycle complete.")
        return {
            "statusCode": 200,
            "body": json.dumps("Detection cycle finished successfully."),
        }

    except Exception as e:
        print(f"FATAL ERROR during anomaly detection: {e}")
        # TODO: Implement backoff and retry for the entire Lambda execution if needed.
        # For now, just send an error notification.
        error_message = f"Flow+WAF Anomaly Detector failed: {str(e)}"
        try:
            # Use a direct SNS publish for error, as notifier.publish_sns expects findings
            boto3.client('sns').publish(
                TopicArn=APP_CONFIG.sns_topic_arn,
                Subject="Flow+WAF Anomaly Detector Error",
                Message=json.dumps({"error": error_message, "context": detection_context}, indent=2)
            )
        except Exception as sns_e:
            print(f"Failed to send error notification to SNS: {sns_e}")
        
        raise # Re-raise the exception so Lambda marks the invocation as failed