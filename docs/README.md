# Flow+WAF Statistics Anomaly Detection

## Overview
A low-cost anomaly detection system for AWS WAF and VPC Flow logs using a serverless architecture (AWS SAM, Lambda, Athena, Glue).

## Features
- **Statistical Anomaly Detection:** Uses EWMA (Exponentially Weighted Moving Average) and 3-sigma rule to detect traffic spikes.
- **IOC Matching:** Correlates anomalous traffic with Indicators of Compromise (IPs, ASNs, regex patterns, etc.).
- **Serverless & Low-Cost:** Built on AWS Lambda, S3, Athena, and Glue for cost-effectiveness.
- **Extensible:** Easily add new detection logic or notification channels.

## Architecture
![Architecture Diagram](images/architecture.png)
*TODO: Add architecture diagram*

1.  **Data Ingestion:**
    *   WAF logs are delivered to an S3 bucket via Kinesis Firehose.
    *   VPC Flow logs are delivered directly to an S3 bucket.
2.  **Data Cataloging:** AWS Glue Crawlers (or manual table definitions) catalog the log data in the Glue Data Catalog.
3.  **Scheduled Detection:** An Amazon EventBridge rule triggers a Lambda function on a regular schedule (e.g., every 5 minutes).
4.  **Query & Analysis:**
    *   The Lambda function executes Athena queries against the log data to aggregate traffic statistics.
    *   The analytics module (`ewma.py`, `aggregators.py`) processes the query results to identify anomalies.
    *   IOCs from `config/ioc.yml` are matched against the anomalous traffic.
5.  **Notification:** If anomalies are detected, a notification is sent via Amazon SNS.

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
*TODO: Add usage instructions*

## Development
*TODO: Add development guidelines*
