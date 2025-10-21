import argparse
import boto3
import time

def run_query(client, query, database, workgroup, bucket):
    """Runs a single Athena query and waits for completion."""
    print(f"Executing query:\n{query}")
    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': f's3://{bucket}/query-results/'},
        WorkGroup=workgroup
    )
    query_execution_id = response['QueryExecutionId']
    print(f"Query Execution ID: {query_execution_id}")

    while True:
        stats = client.get_query_execution(QueryExecutionId=query_execution_id)
        status = stats['QueryExecution']['Status']['State']
        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            print(f"Query finished with status: {status}")
            break
        time.sleep(2)

    if status == 'SUCCEEDED':
        results = client.get_query_results(QueryExecutionId=query_execution_id)
        print("Results:")
        # TODO: Prettier printing (e.g., pandas DataFrame)
        for row in results['ResultSet']['Rows']:
            print([d.get('VarCharValue', 'NULL') for d in row['Data']])
    else:
        print("Query did not succeed.")

def main():
    """Main function to run Athena queries from files."""
    parser = argparse.ArgumentParser(description="Run Athena SQL queries from a file.")
    parser.add_argument("--sql-file", required=True, help="Path to the .sql file.")
    parser.add_argument("--database", required=True, help="Athena database name.")
    parser.add_argument("--workgroup", default="primary", help="Athena workgroup.")
    parser.add_argument("--bucket", required=True, help="S3 bucket for query results.")
    parser.add_argument("--region", default="us-east-1", help="AWS Region.")
    args = parser.parse_args()

    with open(args.sql_file, 'r') as f:
        query_string = f.read()

    athena_client = boto3.client('athena', region_name=args.region)
    run_query(athena_client, query_string, args.database, args.workgroup, args.bucket)

if __name__ == "__main__":
    main()
