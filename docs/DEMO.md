# Demo Guide

This guide walks through a demonstration of the Flow+WAF anomaly detection system.

## 1. Prepare Athena Tables and Partitions

Before running the detector, ensure your Athena tables (`waf_logs`, `vpc_flow_logs`) are correctly set up and that partition projection is working.

1.  **Deploy SAM Application:** If you haven't already, deploy the SAM application as described in `README.md`. This creates the Glue Database and Athena Workgroup.
2.  **Create Glue Tables:** Run the SQL scripts to create the WAF and VPC Flow log tables in Athena.
    ```bash
    python scripts/run_athena.py --sql-file backend/sql/create_db.sql --database flow_waf_log_analysis_db --output-location s3://<your-athena-results-bucket>/query-results/
    python scripts/run_athena.py --sql-file backend/sql/waf_create_table.sql --database flow_waf_log_analysis_db --output-location s3://<your-athena-results-bucket>/query-results/
    python scripts/run_athena.py --sql-file backend/sql/vpc_create_table.sql --database flow_waf_log_analysis_db --output-location s3://<your-athena-results-bucket>/query-results/
    ```
3.  **Verify Partition Projection:** In the Athena console, query `waf_logs` or `vpc_flow_logs`. You should see data if logs are already present in S3. Partition projection should automatically discover new partitions as logs arrive.

## 2. Seed Synthetic Logs

We'll use the `seed_synthetic_logs.py` script to generate and upload synthetic WAF and VPC Flow logs to the corresponding S3 buckets. This will simulate normal traffic and a sudden attack.

```bash
# Generate normal WAF traffic for a few minutes
python scripts/seed_synthetic_logs.py --bucket <your-logs-bucket-name> --mode waf --minutes 5 --rate 10

# Generate normal VPC Flow traffic for a few minutes
python scripts/seed_synthetic_logs.py --bucket <your-logs-bucket-name> --mode vpc --minutes 5 --rate 5

# Introduce a burst of "attack" WAF traffic
python scripts/seed_synthetic_logs.py --bucket <your-logs-bucket-name> --mode waf --minutes 1 --rate 5 --burst-rate-multiplier 10 --burst-duration-seconds 30 --burst-key-value-multiplier 5

# Introduce a burst of "attack" VPC Flow traffic
python scripts/seed_synthetic_logs.py --bucket <your-logs-bucket-name> --mode vpc --minutes 1 --rate 5 --burst-rate-multiplier 10 --burst-duration-seconds 30 --burst-key-value-multiplier 5
```

## Optional: Convert Logs to Parquet (Cost Optimization)

For VPC Flow Logs, converting from JSON to Parquet format can significantly reduce Athena query costs and improve performance. You can use the provided script as a starting point.

```bash
python scripts/convert_to_parquet.py --input-bucket <your-logs-bucket-name> --output-bucket <your-logs-bucket-name> --log-type vpc --database flow_waf_log_analysis_db
```

*Note: After converting, you would typically create a new Athena table pointing to the Parquet files and update your Detector Lambda to query this new table for VPC Flow Logs.*

For a more realistic test, you can use a load testing tool like `vegeta` or `ab` to generate traffic against a test endpoint protected by the WAF. This will produce actual WAF logs.

Refer to `scripts/vegeta_scenario.md` for an example scenario using `vegeta`.

## 4. Manually Execute the Detector Lambda

Instead of waiting for the scheduled EventBridge trigger, you can invoke the `DetectorFunction` Lambda manually from the AWS Console or using the AWS CLI. This will trigger an immediate detection run.

```bash
aws lambda invoke --function-name <YourStackName>-AnomalyDetector --payload '{}' response.json --log-type Tail --query 'LogResult' --output text | base64 -d
```
Check the `response.json` file and the decoded log output for execution details.

## 5. Observe Notifications and Metrics

If anomalies were detected, the detector function will publish notifications and metrics.

*   **SNS Notification:**
    *   Check the email inbox subscribed to your SNS topic. You should receive an email with details of the detected anomalies.
    *   *Screenshot Placeholder: Add a screenshot of an example SNS email notification here.*
*   **Slack Notification (if configured):**
    *   If you configured a Slack webhook URL, check your Slack channel for anomaly alerts.
    *   *Screenshot Placeholder: Add a screenshot of an example Slack notification here.*
*   **CloudWatch Metrics (EMF):**
    *   Navigate to CloudWatch Metrics in the AWS Console.
    *   Look for the `FlowWAFSentinel` namespace. You should see metrics like `AnomalyCount` and `MaxAnomalyScore`.
    *   *Screenshot Placeholder: Add a screenshot of CloudWatch Metrics dashboard showing anomaly metrics here.*

## 6. Tuning and Comparison (α, σ)

The sensitivity of the anomaly detection can be adjusted by tuning the `EWMA_ALPHA` and `SIGMA` parameters in your `infra/sam-template.yaml`.

*   **`EWMA_ALPHA`**:
    *   Higher values (e.g., 0.5-0.9): More responsive to recent changes, detects sudden spikes quickly but might be more prone to false positives from normal fluctuations.
    *   Lower values (e.g., 0.1-0.3): Smoother, less sensitive to short-term changes, better for detecting sustained shifts but might be slower to react to sudden bursts.
*   **`SIGMA`**:
    *   Higher values (e.g., 3.5-5.0): Less sensitive, fewer false positives, but might miss subtle anomalies.
    *   Lower values (e.g., 2.0-2.5): More sensitive, detects more anomalies, but might increase false positives.

**Experiment:**
1.  Modify `EWMA_ALPHA` or `SIGMA` in `infra/sam-template.yaml`.
2.  Redeploy the SAM application (`sam deploy`).
3.  Generate synthetic logs with a known burst.
4.  Manually execute the Detector Lambda.
5.  Observe how the number and score of detected anomalies change with different tuning parameters.