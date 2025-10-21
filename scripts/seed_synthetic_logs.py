import argparse
import json
import datetime
import random
import boto3

# TODO:
# - Expand with more realistic log variations.
# - Add VPC Flow Log generation.

def generate_waf_log_entry(timestamp, ip, uri, ua, country, label=None):
    """Generates a single WAF log entry."""
    return {
        "timestamp": timestamp,
        "formatVersion": 1,
        "webaclId": "arn:aws:wafv2:us-east-1:123456789012:regional/webacl/test-acl/",
        "terminatingRule": {
            "ruleId": "rule-id-1",
            "action": "BLOCK" if label else "ALLOW",
        },
        "httpRequest": {
            "clientIp": ip,
            "country": country,
            "headers": [
                {"name": "User-Agent", "value": ua}
            ],
            "uri": uri,
            "method": "GET",
        },
        "httpResponse": {
            "statusCode": 403 if label else 200
        },
        "labels": [{"name": label}] if label else []
    }

def main():
    """Main function to generate and upload logs."""
    parser = argparse.ArgumentParser(description="Seed S3 with synthetic WAF logs.")
    parser.add_argument("--bucket", required=True, help="S3 bucket name for WAF logs.")
    parser.add_argument("--region", default="us-east-1", help="AWS Region.")
    parser.add_argument("--traffic-type", choices=['normal', 'attack'], default='normal', help="Type of traffic to generate.")
    parser.add_argument("--count", type=int, default=100, help="Number of log entries.")
    args = parser.parse_args()

    s3 = boto3.client('s3', region_name=args.region)
    now = datetime.datetime.utcnow()

    print(f"Generating {args.count} '{args.traffic_type}' log entries...")

    log_data = []
    for i in range(args.count):
        ts = int(now.timestamp() * 1000)
        if args.traffic_type == 'attack':
            ip = f"10.10.10.{random.randint(1, 254)}"
            uri = "/api/v1/users?id=' OR 1=1 --"
            ua = "sqlmap/1.5"
            country = "KP"
            label = "awswaf:managed:aws:sql-database"
        else: # normal
            ip = f"203.0.113.{random.randint(1, 254)}"
            uri = f"/items/{random.randint(1, 100)}"
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            country = "US"
            label = None

        log_entry = generate_waf_log_entry(ts, ip, uri, ua, country, label)
        log_data.append(json.dumps(log_entry))

    # Firehose format: multiple JSON objects concatenated in one file
    content = "\n".join(log_data) + "\n"

    # S3 path format for Firehose: YYYY/MM/DD/HH/file-name
    key = now.strftime(f"%Y/%m/%d/%H/synthetic-logs-{now.isoformat()}.log")

    print(f"Uploading to s3://{args.bucket}/{key}")
    # s3.put_object(Bucket=args.bucket, Key=key, Body=content)
    print("TODO: S3 upload is commented out. Uncomment to enable.")
    print("Done.")


if __name__ == "__main__":
    main()
