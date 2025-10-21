# Flow+WAF Statistics Anomaly Detection
[![CI/CD Pipeline](https://github.com/jijae92/FlowWAF/actions/workflows/ci.yml/badge.svg)](https://github.com/jijae92/FlowWAF/actions/workflows/ci.yml)

## Overview
A low-cost anomaly detection system for AWS WAF and VPC Flow logs using a serverless architecture (AWS SAM, Lambda, Athena, Glue). It leverages statistical methods (EWMA, 3-sigma rule) and Indicators of Compromise (IOC) matching to identify suspicious traffic patterns.

## Features
- **Statistical Anomaly Detection:** Uses EWMA (Exponentially Weighted Moving Average) and 3-sigma rule to detect traffic spikes.
- **IOC Matching:** Correlates anomalous traffic with Indicators of Compromise (IPs, ASNs, regex patterns, etc.) defined in `config/ioc.yml`.
- **Serverless & Low-Cost:** Built on AWS Lambda, S3, Athena, and Glue for cost-effectiveness, paying only for what you use.
- **Extensible:** Easily add new detection logic or notification channels (SNS, Slack, CloudWatch EMF).
- **Automated Baseline Management:** Baselines for normal traffic patterns are automatically learned and updated in S3.

## Architecture
The system processes WAF and VPC Flow logs to detect anomalies.

```mermaid
graph TD
    subgraph "Log Sources"
        WAF[AWS WAF Logs] --> KFH(Kinesis Firehose)
        VPC[VPC Flow Logs] --> S3Logs(S3 Logs Bucket)
    end

    KFH --> S3Logs
    S3Logs --> Glue(AWS Glue Data Catalog)
    S3Logs -- "Athena Query Results" --> S3Athena(S3 Athena Results Bucket)

    subgraph "Anomaly Detection Pipeline"
        EB(EventBridge Scheduler) --> LambdaDetector(Detector Lambda)
        LambdaDetector -- "SQL Queries" --> Athena(AWS Athena)
        Athena -- "Query Results" --> LambdaDetector
        LambdaDetector -- "Baselines" --> S3Logs
        LambdaDetector -- "Notifications" --> SNS(SNS Topic)
        LambdaDetector -- "Metrics" --> CWM(CloudWatch Metrics)
        LambdaDetector -- "Optional" --> Slack(Slack Webhook)
    end

    SNS --> "Email/SMS/Other Subscriptions"
    CWM --> "Monitoring/Alerting"

    style WAF fill:#f9f,stroke:#333,stroke-width:2px
    style VPC fill:#f9f,stroke:#333,stroke-width:2px
    style KFH fill:#bbf,stroke:#333,stroke-width:2px
    style S3Logs fill:#bbf,stroke:#333,stroke-width:2px
    style Glue fill:#bbf,stroke:#333,stroke-width:2px
    style S3Athena fill:#bbf,stroke:#333,stroke-width:2px
    style EB fill:#bbf,stroke:#333,stroke-width:2px
    style LambdaDetector fill:#bbf,stroke:#333,stroke-width:2px
    style Athena fill:#bbf,stroke:#333,stroke-width:2px
    style SNS fill:#bbf,stroke:#333,stroke-width:2px
    style CWM fill:#bbf,stroke:#333,stroke-width:2px
    style Slack fill:#bbf,stroke:#333,stroke-width:2px
```

## Quick Start

Follow these steps to get the anomaly detection system up and running quickly.

1.  **Install Dependencies:**
    ```bash
    make install
    ```

2.  **Deploy AWS SAM Application:**
    This will deploy the Lambda functions, S3 buckets, SNS topic, Athena Workgroup, and EventBridge rule.
    ```bash
    make build
    sam deploy --guided
    ```
    *During `sam deploy --guided`, ensure you provide appropriate values for parameters like `LogsBucketName`, `AthenaResultsBucketName`, and `SlackWebhookUrl` if you intend to use Slack notifications.*

3.  **Create Athena Tables:**
    After deployment, you need to create the Glue tables that Athena will query. You can do this by running the SQL scripts manually in the Athena console or via a utility script.
    ```bash
    # Example using the run_athena.py script (ensure you have AWS credentials configured)
    python scripts/run_athena.py --sql-file backend/sql/create_db.sql --database flow_waf_log_analysis_db --output-location s3://<your-athena-results-bucket>/query-results/
    python scripts/run_athena.py --sql-file backend/sql/waf_create_table.sql --database flow_waf_log_analysis_db --output-location s3://<your-athena-results-bucket>/query-results/
    python scripts/run_athena.py --sql-file backend/sql/vpc_create_table.sql --database flow_waf_log_analysis_db --output-location s3://<your-athena-results-bucket>/query-results/
    # Replace <your-athena-results-bucket> with the actual bucket name from `sam deploy` outputs.
    ```

4.  **Seed Synthetic Logs (for testing/demo):**
    Generate some synthetic WAF or VPC Flow logs and upload them to your S3 logs bucket. This will simulate traffic for the detector.
    ```bash
    python scripts/seed_synthetic_logs.py --bucket <your-logs-bucket-name> --mode waf --minutes 10 --rate 5 --burst-rate-multiplier 10 --burst-duration-seconds 60
    python scripts/seed_synthetic_logs.py --bucket <your-logs-bucket-name> --mode vpc --minutes 10 --rate 5 --burst-rate-multiplier 10 --burst-duration-seconds 60
    ```

5.  **Manually Execute Detector Lambda:**
    To trigger an immediate detection run without waiting for the EventBridge schedule, you can manually invoke the `DetectorFunction` from the AWS Lambda console or using the AWS CLI.
    ```bash
    aws lambda invoke --function-name <YourStackName>-AnomalyDetector --payload '{}' response.json
    ```

## Configuration and Tuning

The behavior of the anomaly detection can be tuned using the following parameters in `infra/sam-template.yaml` (and exposed as environment variables to the Lambda functions):

*   **`LOOKBACK_MINUTES`**: (Default: 15) The time window (in minutes) for which Athena queries aggregate log data. This defines the "current" data window for anomaly detection.
*   **`TRAIN_DAYS`**: (Default: 7) The number of days of historical data used to initially train the EWMA baseline for new metrics/keys.
*   **`EWMA_ALPHA`**: (Default: 0.3) The smoothing factor (alpha) for the Exponentially Weighted Moving Average. A higher alpha (closer to 1) makes the EWMA more responsive to recent changes, while a lower alpha (closer to 0) makes it smoother and less sensitive.
*   **`SIGMA`**: (Default: 3.0) The number of standard deviations from the EWMA mean that a data point must exceed to be considered an anomaly (3-sigma rule). Adjust this to control the sensitivity of detection.
*   **`TOP_K`**: (Default: 100) The maximum number of top aggregated entities (e.g., top IPs, URIs) to consider for anomaly detection in each run.
*   **`ATHENA_QUERY_TIMEOUT_SECONDS`**: (Default: 120) Maximum duration (in seconds) for Athena queries before timing out. Prevents long-running queries from consuming excessive Lambda execution time.
*   **`MAX_SCANNED_BYTES_MB`**: (Default: 256) Maximum amount of data (in MB) Athena queries can scan before being cancelled. Helps control costs and prevent runaway queries.
*   **`SNS_TOPIC_ARN`**: The ARN of the SNS topic for anomaly notifications.
*   **`SLACK_WEBHOOK_URL`**: (Optional) Slack webhook URL for notifications. Leave empty to disable Slack notifications.

### Failure and Limit Handling

*   **Baseline Cold Start (`TRAIN_DAYS`):** When a new `(metric, key, subkey)` combination is encountered for which no baseline exists, the system enters a "bootstrap" or "training" mode. It will use `TRAIN_DAYS` worth of historical data (if available) to establish an initial baseline before actively detecting anomalies. Until a stable baseline is formed, anomalies for this specific key might not be detected or might be less accurate.
*   **Athena Query Limits:** `ATHENA_QUERY_TIMEOUT_SECONDS` and `MAX_SCANNED_BYTES_MB` are configured to prevent excessive costs and Lambda timeouts. If a query exceeds these limits, it will be cancelled, and an error notification will be sent via SNS.

### Advanced Tuning and Extension Points

*   **Spike vs. Step Changes:** The current EWMA model is effective for detecting sudden spikes. For detecting more gradual, step-like changes, consider adding a comparison with a longer-term moving average or implementing a CUSUM (Cumulative Sum) algorithm. (TODO: Explore adding CUSUM or other change-point detection algorithms).
*   **IOC Matching Score Weighting:** When an anomaly is also matched by an IOC, its anomaly score could be weighted higher to prioritize known malicious patterns. (TODO: Implement score weighting for IOC matches in `ewma.py`).
*   **Dynamic Alpha/Sigma:** For highly volatile metrics, consider dynamically adjusting `EWMA_ALPHA` or `SIGMA` based on recent data variance. (TODO: Research and implement adaptive EWMA parameters).
*   **Partition Strategy**: The Athena tables (`waf_logs`, `vpc_flow_logs`) are partitioned by `dt` (date) and `hr` (hour). This is crucial for cost-effective querying as Athena only scans data in specified partitions. Ensure your log ingestion (Firehose, direct S3 uploads) writes data to S3 paths matching this partitioning scheme (e.g., `s3://your-bucket/waf-logs/dt=YYYY-MM-DD/hr=HH/`).

## Optional Optimizations

This section outlines additional optimizations you can implement for further cost reduction and performance enhancement.

### 1. Parquet Conversion for VPC Flow Logs

While WAF logs are often JSON, converting VPC Flow Logs to Parquet format can significantly reduce Athena query costs and improve performance. Parquet is a columnar storage format that allows Athena to read only the necessary columns.

*   **Implementation:** You can use a dedicated AWS Glue ETL job or a Lambda function (e.g., `scripts/convert_to_parquet.py`) to periodically convert new JSON VPC Flow logs to Parquet and store them in a separate S3 prefix. You would then create a new Athena table pointing to these Parquet files.
*   **Script Example:** See `scripts/convert_to_parquet.py` for a basic example of how to convert JSON logs to Parquet.

### 2. Enhanced Partition Management

Partition Projection is enabled on both WAF and VPC Flow log tables in the SAM template. This automatically manages partitions, eliminating the need for `MSCK REPAIR TABLE` and ensuring Athena only scans relevant data.

*   **Configuration Reference:** The partition projection settings are defined directly within the Glue Table resources in `infra/sam-template.yaml`. You can refer to the structure in `config/partition-projection.json` for a conceptual understanding of how these settings work.

### 3. Dynamic Query String Substitution

The `DetectorFunction` automatically substitutes variables like `${LOOKBACK_MINUTES}`, `${TOP_K}`, and `${database_name}` directly into the SQL query strings before execution. This allows for flexible and dynamic query generation based on environment variables configured in the Lambda function.

## Cost Optimization Strategies

Beyond the optional optimizations, the serverless architecture itself is designed with cost-effectiveness in mind. Here are key strategies:

*   **S3 Lifecycle Policies:** Configured on `LogsBucket` (90 days) and `AthenaResultsBucket` (30 days), these policies automatically transition older data to cheaper storage classes (like Glacier) or delete it, optimizing storage costs.
*   **Event-Driven & Serverless:** Lambda and Athena are billed per invocation/query and data scanned, respectively, ensuring you only pay for actual usage.

## Security and Compliance Considerations

*   **Logging and Retention:** All WAF and VPC Flow logs are centralized in S3, providing a durable and auditable record. S3 lifecycle policies manage retention.
*   **Alerting:** Anomalies trigger SNS notifications, which can be integrated with various alerting mechanisms (email, PagerDuty, custom webhooks).
*   **Change Management:** The entire infrastructure is defined as Infrastructure as Code (IaC) using AWS SAM, enabling version control, peer review, and automated deployment for all changes.
*   **Least Privilege:** IAM roles for Lambda and Firehose are configured with the principle of least privilege, granting only necessary permissions. (TODO: Further scope down Athena/Glue permissions to specific resources).
*   **IOC Management:** Indicators of Compromise are managed in `config/ioc.yml`, allowing for easy updates and version control of threat intelligence.

## Continuous Integration (CI)
This project uses GitHub Actions for continuous integration. The CI pipeline automatically runs on every push and pull request to the `main` branch.

The CI workflow performs the following checks:
-   **Code Linting:** Ensures code quality and adherence to style guidelines using `ruff`.
-   **Unit Tests:** Executes all unit tests with `pytest` and checks code coverage.
-   **CloudFormation Linting:** Validates the AWS SAM template using `cfn-lint`.
-   **SAM Validation:** Builds and validates the SAM application using `sam build` and `sam validate`.

You can view the status of the CI pipeline on the GitHub repository's Actions tab.

## Deployment
This project uses AWS SAM.

1.  **Prerequisites:**
    *   AWS CLI
    *   AWS SAM CLI
    *   Python 3.11
    *   Docker (for `sam build`)

2.  **Installation:**
    ```bash
    make install
    ```

3.  **Build & Deploy:**
    ```bash
    make build
    sam deploy --guided
    ```

## Usage
*TODO: Add more detailed usage instructions for specific scenarios.*

## Development
*TODO: Add development guidelines*
