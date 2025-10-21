# Demo Guide

This guide walks through a demonstration of the Flow+WAF anomaly detection system.

## 1. Seed Synthetic Logs

We'll use a script to generate and upload synthetic WAF and VPC Flow logs to the corresponding S3 buckets. This will simulate normal traffic and a sudden attack.

```bash
# TODO: Implement the seeding script
python scripts/seed_synthetic_logs.py --traffic-type normal
python scripts/seed_synthetic_logs.py --traffic-type attack
```

## 2. Manual Detector Invocation

Instead of waiting for the scheduled EventBridge trigger, we can invoke the detector Lambda function manually from the AWS Console or using the AWS CLI.

This will trigger the Athena queries and the detection logic.

## 3. Check Athena Query History

Navigate to the Athena service in the AWS Console. You can see the queries executed by the Lambda function in the "History" tab. This is useful for debugging.

## 4. Observe SNS Notification

If an anomaly was detected, the detector function publishes a message to an SNS topic.

- Check the associated email inbox (if you subscribed an email endpoint).
- Check the CloudWatch Logs for the `detector_handler` Lambda to see the notification payload.

## 5. Load Testing Scenario (Optional)

For a more realistic test, you can use a load testing tool like `vegeta` to generate traffic against a test endpoint protected by the WAF.

See `scripts/vegeta_scenario.md` for an example scenario.
