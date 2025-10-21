import argparse
import boto3
import time
import pandas as pd
from typing import Dict, Any

# TODO:
# - Add error handling and retry logic.
# - Make output location configurable.
# - Add support for different output formats (e.g., CSV, JSON).

def run_athena_query_and_fetch_results(
    athena_client: Any,
    query_string: str,
    database: str,
    workgroup: str,
    output_location: str,
    poll_interval_seconds: int = 5,
    max_poll_attempts: int = 60 # 5 minutes
) -> pd.DataFrame:
    """
    Executes an Athena query, waits for completion, and fetches results into a Pandas DataFrame.

    Args:
        athena_client: Boto3 Athena client.
        query_string (str): The SQL query string to execute.
        database (str): The Athena database to query.
        workgroup (str): The Athena workgroup to use.
        output_location (str): S3 path for query results (e.g., 's3://your-bucket/path/').
        poll_interval_seconds (int): How often to poll for query status.
        max_poll_attempts (int): Maximum number of polling attempts before giving up.

    Returns:
        pd.DataFrame: A DataFrame containing the query results.

    Raises:
        Exception: If the Athena query fails or times out.
    """
    print(f"Starting Athena query in database '{database}', workgroup '{workgroup}'...")
    print(f"Query (first 200 chars): {query_string[:200]}...")

    response = athena_client.start_query_execution(
        QueryString=query_string,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': output_location},
        WorkGroup=workgroup
    )
    query_execution_id = response['QueryExecutionId']
    print(f"Query Execution ID: {query_execution_id}")

    # Polling for query completion
    state = 'RUNNING'
    attempts = 0
    while state in ['RUNNING', 'QUEUED'] and attempts < max_poll_attempts:
        time.sleep(poll_interval_seconds)
        query_status = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        state = query_status['QueryExecution']['Status']['State']
        print(f"Query status: {state} (Attempt {attempts + 1}/{max_poll_attempts})")
        attempts += 1

    if state == 'SUCCEEDED':
        # Fetch results
        results_paginator = athena_client.get_paginator('get_query_results')
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
        raise Exception(f"Athena query failed or timed out. State: {state}, Reason: {failure_reason}")

def main():
    parser = argparse.ArgumentParser(description="Run Athena SQL queries and fetch results.")
    parser.add_argument("--sql-file", required=True, help="Path to the .sql file containing the query.")
    parser.add_argument("--database", required=True, help="Athena database name.")
    parser.add_argument("--workgroup", default="primary", help="Athena workgroup.")
    parser.add_argument("--output-location", required=True, help="S3 path for query results (e.g., 's3://your-bucket/path/').")
    parser.add_argument("--region", default="us-east-1", help="AWS Region.")
    args = parser.parse_args()

    athena_client = boto3.client('athena', region_name=args.region)

    with open(args.sql_file, 'r') as f:
        query_string = f.read()
    
    # TODO: Implement variable substitution for SQL queries if needed (e.g., ${LOOKBACK_MINUTES})

    try:
        df_results = run_athena_query_and_fetch_results(
            athena_client,
            query_string,
            args.database,
            args.workgroup,
            args.output_location
        )
        print("\n--- Query Results ---")
        print(df_results.to_string())
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()