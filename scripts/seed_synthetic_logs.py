import argparse
import json
import datetime
import random
import boto3
import time
import uuid

# TODO:
# - More sophisticated log generation for WAF and VPC Flow.
# - Handle different log formats (e.g., CLF for WAF, different VPC Flow versions).
# - Make S3 bucket configurable via environment variables or CLI.

def generate_waf_log_entry(timestamp_ms, ip, uri, ua, country, label=None):
    """Generates a single WAF log entry (simplified)."""
    return {
        "timestamp": timestamp_ms,
        "formatVersion": 1,
        "webaclId": "arn:aws:wafv2:us-east-1:123456789012:regional/webacl/test-acl/",
        "terminatingRule": {
            "ruleId": "rule-id-1",
            "action": "ALLOW",
        },
        "httpRequest": {
            "clientIp": ip,
            "country": country,
            "headers": [
                {"name": "User-Agent", "value": ua}
            ],
            "uri": uri,
            "method": "GET",
            "httpVersion": "HTTP/1.1",
            "requestId": str(uuid.uuid4())
        },
        "httpResponse": {
            "statusCode": 200
        },
        "labels": [{"name": label}] if label else []
    }

def generate_vpc_flow_log_entry(timestamp_s, srcaddr, dstaddr, srcport, dstport, action, packets, bytes_val):
    """Generates a single VPC Flow log entry (simplified)."""
    return {
        "version": 2,
        "account-id": "123456789012",
        "interface-id": "eni-0abcdef1234567890",
        "srcaddr": srcaddr,
        "dstaddr": dstaddr,
        "srcport": srcport,
        "dstport": dstport,
        "protocol": 6, # TCP
        "packets": packets,
        "bytes": bytes_val,
        "start": timestamp_s,
        "end": timestamp_s + 5, # 5 seconds duration
        "action": action,
        "log-status": "OK"
    }

def main():
    parser = argparse.ArgumentParser(description="Seed S3 with synthetic WAF or VPC Flow logs.")
    parser.add_argument("--bucket", required=True, help="S3 bucket name for logs.")
    parser.add_argument("--mode", choices=['waf', 'vpc'], required=True, help="Type of logs to generate (waf or vpc).")
    parser.add_argument("--minutes", type=int, default=5, help="Duration in minutes for log generation.")
    parser.add_argument("--rate", type=int, default=10, help="Average log entries per second.")
    parser.add_argument("--burst-rate-multiplier", type=int, default=5, help="Multiplier for burst traffic rate.")
    parser.add_argument("--burst-duration-seconds", type=int, default=30, help="Duration of burst in seconds.")
    parser.add_argument("--burst-key-value-multiplier", type=int, default=5, help="Multiplier for specific key value during burst (x3-x10).")
    parser.add_argument("--region", default="us-east-1", help="AWS Region.")
    args = parser.parse_args()

    s3 = boto3.client('s3', region_name=args.region)
    
    start_time = datetime.datetime.utcnow()
    end_time = start_time + datetime.timedelta(minutes=args.minutes)

    print(f"Generating {args.mode} logs for {args.minutes} minutes at {args.rate} req/s (avg)...")

    log_entries = []
    current_time = start_time
    burst_active = False
    burst_start = None

    # Define a specific key/value to burst
    burst_ip = "10.0.0.100"
    burst_uri = "/attack/path"
    burst_ua = "BadBot/1.0"
    burst_dstport = 8080

    while current_time < end_time:
        # Check for burst window
        if not burst_active and random.random() < 0.1: # 10% chance to start a burst
            burst_active = True
            burst_start = current_time
            print(f"--- BURST START at {current_time} ---")
        
        if burst_active and (current_time - burst_start).total_seconds() > args.burst_duration_seconds:
            burst_active = False
            print(f"--- BURST END at {current_time} ---")

        current_rate = args.rate * args.burst_rate_multiplier if burst_active else args.rate
        num_logs_in_second = int(current_rate * (1 + (random.random() - 0.5) * 0.5)) # +/- 25% variation

        for _ in range(num_logs_in_second):
            timestamp_ms = int(current_time.timestamp() * 1000)
            timestamp_s = int(current_time.timestamp())

            if args.mode == 'waf':
                ip = f"203.0.113.{random.randint(1, 254)}"
                uri = f"/items/{random.randint(1, 100)}"
                ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                country = random.choice(["US", "KR", "JP", "CN"])
                label = None

                if burst_active and random.random() < 0.7: # 70% of burst traffic is "bad"
                    ip = burst_ip
                    uri = burst_uri
                    ua = burst_ua
                    # Increase value for this specific key during burst
                    for _ in range(args.burst_key_value_multiplier - 1):
                        log_entries.append(json.dumps(generate_waf_log_entry(timestamp_ms, ip, uri, ua, country, "burst-label")))
                
                log_entries.append(json.dumps(generate_waf_log_entry(timestamp_ms, ip, uri, ua, country, label)))

            elif args.mode == 'vpc':
                srcaddr = f"172.31.{random.randint(0, 255)}.{random.randint(1, 254)}"
                dstaddr = f"10.0.{random.randint(0, 255)}.{random.randint(1, 254)}"
                srcport = random.randint(1024, 65535)
                dstport = random.choice([80, 443, 22, 3389])
                action = random.choice(["ACCEPT", "REJECT"])
                packets = random.randint(10, 100)
                bytes_val = packets * random.randint(50, 100)

                if burst_active and random.random() < 0.7: # 70% of burst traffic is "bad"
                    srcaddr = burst_ip # Re-use burst_ip for VPC srcaddr
                    dstport = burst_dstport
                    action = "REJECT"
                    # Increase value for this specific key during burst
                    for _ in range(args.burst_key_value_multiplier - 1):
                        log_entries.append(json.dumps(generate_vpc_flow_log_entry(timestamp_s, srcaddr, dstaddr, srcport, dstport, action, packets * 2, bytes_val * 2)))

                log_entries.append(json.dumps(generate_vpc_flow_log_entry(timestamp_s, srcaddr, dstaddr, srcport, dstport, action, packets, bytes_val)))
        
        current_time += datetime.timedelta(seconds=1)
        # Simulate real-time generation
        # time.sleep(1) # Commented out for faster generation during testing

    # Upload logs to S3
    if log_entries:
        # S3 path format for Firehose/VPC Flow: dt=YYYY-MM-DD/hr=HH/file-name
        upload_time = datetime.datetime.utcnow()
        dt_path = upload_time.strftime("dt=%Y-%m-%d")
        hr_path = upload_time.strftime("hr=%H")
        
        if args.mode == 'waf':
            prefix = "waf-logs"
        else: # vpc
            prefix = "vpc-flow-logs"

        key = f"{prefix}/{dt_path}/{hr_path}/{args.mode}-{upload_time.isoformat()}.json"
        content = "\n".join(log_entries) + "\n"

        print(f"Uploading {len(log_entries)} {args.mode} log entries to s3://{args.bucket}/{key}")
        try:
            s3.put_object(Bucket=args.bucket, Key=key, Body=content)
            print("Upload complete.")
        except Exception as e:
            print(f"Error uploading to S3: {e}")
    else:
        print("No log entries generated.")

if __name__ == "__main__":
    main()