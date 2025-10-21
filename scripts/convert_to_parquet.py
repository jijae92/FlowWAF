import argparse
import boto3
import pandas as pd
import awswrangler as wr
from datetime import datetime, timedelta

# TODO:
# - Implement robust error handling and logging.
# - Add support for incremental conversion (only new partitions).
# - Make Glue database/table names configurable.
# - Consider using AWS Glue ETL jobs for production-grade conversions.

def convert_s3_json_to_parquet(
    s3_input_path: str,
    s3_output_path: str,
    database: str,
    table: str,
    partition_cols: list,
    region: str = "us-east-1"
):
    """
    Reads JSON data from S3, converts it to Parquet, and writes back to S3.
    Also updates Glue table partitions.
    """
    print(f"Converting data from {s3_input_path} to Parquet in {s3_output_path}...")
    
    # Example: Read data for the last day
    # In a real scenario, you'd iterate through partitions or use Glue triggers.
    today = datetime.now()
    year = today.strftime("%Y")
    month = today.strftime("%m")
    day = today.strftime("%d")
    
    # Construct input path for a specific partition (example)
    # This needs to be dynamic based on how logs are ingested
    input_path_for_day = f"{s3_input_path}/dt={year}-{month}-{day}/" # Assuming dt=YYYY-MM-DD
    
    try:
        # Read JSON data
        df = wr.s3.read_json(path=input_path_for_day, dataset=True, path_suffix=".json")
        
        if df.empty:
            print(f"No JSON data found in {input_path_for_day}. Skipping conversion.")
            return

        # Write to Parquet
        wr.s3.to_parquet(
            df=df,
            path=s3_output_path,
            dataset=True,
            database=database,
            table=table,
            partition_cols=partition_cols,
            mode="append" # Append to existing Parquet dataset
        )
        print(f"Successfully converted and wrote {len(df)} records to Parquet.")

        # TODO: Add logic to remove original JSON files after successful conversion
        
    except Exception as e:
        print(f"Error during conversion: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Convert S3 JSON logs to Parquet format.")
    parser.add_argument("--input-bucket", required=True, help="S3 bucket for input JSON logs.")
    parser.add_argument("--output-bucket", required=True, help="S3 bucket for output Parquet logs.")
    parser.add_argument("--log-type", choices=['waf', 'vpc'], required=True, help="Type of logs (waf or vpc).")
    parser.add_argument("--database", default="security_analytics", help="Glue database name.")
    parser.add_argument("--region", default="us-east-1", help="AWS Region.")
    args = parser.parse_args()

    if args.log_type == 'waf':
        json_prefix = "waf-logs"
        parquet_prefix = "waf-logs-parquet" # New prefix for Parquet
        table_name = "waf_logs_parquet" # New table for Parquet
        partition_cols = ['dt', 'hr']
    else: # vpc
        json_prefix = "vpc-flow-logs"
        parquet_prefix = "vpc-flow-logs-parquet"
        table_name = "vpc_flow_logs_parquet"
        partition_cols = ['dt', 'hr'] # Assuming VPC Flow also partitioned by dt/hr

    s3_input_path = f"s3://{args.input_bucket}/{json_prefix}/"
    s3_output_path = f"s3://{args.output_bucket}/{parquet_prefix}/"

    convert_s3_json_to_parquet(
        s3_input_path,
        s3_output_path,
        args.database,
        table_name,
        partition_cols,
        args.region
    )

if __name__ == "__main__":
    main()
