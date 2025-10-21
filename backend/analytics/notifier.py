import json
import os
import requests
import boto3
from typing import List, Dict, Any
from datetime import datetime

# TODO: Initialize boto3 clients outside the function for better performance in Lambda
SNS_CLIENT = boto3.client('sns')
# CloudWatch EMF requires specific formatting, often handled by a library like aws-embedded-metrics
# For simplicity, we'll simulate or use a basic put_metric_data if EMF library is not used.
# If using aws-embedded-metrics, it would be:
# from aws_embedded_metrics import get_metrics
# metrics = get_metrics()

def publish_sns(topic_arn: str, findings: List[Dict[str, Any]], context: Dict[str, Any]):
    """
    Publishes anomaly findings to an AWS SNS topic.

    Args:
        topic_arn (str): The ARN of the SNS topic.
        findings (List[Dict[str, Any]]): A list of anomaly findings.
        context (Dict[str, Any]): Additional context information (e.g., timestamp, source).
    """
    subject = f"Flow+WAF Anomaly Detected ({len(findings)} findings)"
    message_payload = {
        "subject": subject,
        "findings": findings,
        "context": context,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    try:
        SNS_CLIENT.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=json.dumps(message_payload, indent=2),
            MessageStructure='string' # 'json' requires subscription confirmation
        )
        print(f"Successfully published {len(findings)} findings to SNS topic: {topic_arn}")
    except Exception as e:
        print(f"Error publishing to SNS topic {topic_arn}: {e}")
        # TODO: Add more robust error handling, e.g., dead-letter queue

def format_slack(findings: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Formats anomaly findings into a Slack message payload.

    Args:
        findings (List[Dict[str, Any]]): A list of anomaly findings.
        context (Dict[str, Any]): Additional context information.

    Returns:
        Dict[str, Any]: A dictionary representing the Slack message payload.
    """
    if not findings:
        return {"text": "No anomalies detected."}

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🚨 Flow+WAF Anomaly Detected ({len(findings)} findings) 🚨"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Detection Time:* {context.get('timestamp', 'N/A')}\n*Source:* {context.get('source', 'N/A')}"
            }
        },
        {"type": "divider"}
    ]

    for i, finding in enumerate(findings):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{i+1}. Metric:* `{finding.get('metric', 'N/A')}`\n"
                    f"*Key:* `{finding.get('key', 'N/A')}`\n"
                    f"*Subkey:* `{finding.get('subkey', 'N/A')}`\n"
                    f"*Value:* `{finding.get('value', 'N/A')}`\n"
                    f"*Score (Sigma):* `{finding.get('score', 'N/A'):.2f}` ({finding.get('mode', 'N/A')})\n"
                    f"*Baseline Mean:* `{finding.get('baseline_mean', 'N/A'):.2f}`\n"
                    f"*Baseline StdDev:* `{finding.get('baseline_std', 'N/A'):.2f}`\n"
                )
            }
        })
        if finding.get('ioc_matches'):
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*IOC Matches:* {', '.join(finding['ioc_matches'])}"
                    }
                ]
            })
        blocks.append({"type": "divider"})

    return {"blocks": blocks}

def send_slack_notification(webhook_url: str, findings: List[Dict[str, Any]], context: Dict[str, Any]):
    """
    Sends anomaly findings to a Slack channel via webhook.

    Args:
        webhook_url (str): The Slack webhook URL.
        findings (List[Dict[str, Any]]): A list of anomaly findings.
        context (Dict[str, Any]): Additional context information.
    """
    if not webhook_url:
        print("Slack webhook URL not configured. Skipping Slack notification.")
        return

    payload = format_slack(findings, context)
    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        response.raise_for_status()
        print(f"Successfully sent {len(findings)} findings to Slack.")
    except requests.exceptions.RequestException as e:
        print(f"Error sending Slack notification: {e}")
        # TODO: Add retry logic or dead-letter queue

def emit_emf(namespace: str, dimensions: Dict[str, str], metrics: Dict[str, float]):
    """
    Emits CloudWatch Embedded Metric Format (EMF) logs.
    This function assumes the Lambda environment is configured to process EMF logs.
    Metrics will appear in CloudWatch Metrics under the specified namespace and dimensions.

    Args:
        namespace (str): The CloudWatch namespace for the metrics.
        dimensions (Dict[str, str]): A dictionary of dimensions for the metrics.
        metrics (Dict[str, float]): A dictionary of metric names and their values.
    """
    # EMF logs are JSON objects written to stdout.
    # The Lambda runtime environment (e.g., with Lambda PowerTools) automatically
    # parses these and sends them to CloudWatch Metrics.
    # If not using PowerTools, this is a basic manual construction.
    emf_log = {
        "_aws": {
            "Timestamp": int(datetime.utcnow().timestamp() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": namespace,
                    "Dimensions": [list(dimensions.keys())],
                    "Metrics": [{"Name": name, "Unit": "Count"} for name in metrics.keys()]
                }
            ]
        }
    }
    # Add dimensions and metrics to the root of the log object
    emf_log.update(dimensions)
    emf_log.update(metrics)

    print(json.dumps(emf_log))
    print(f"Emitted {len(metrics)} EMF metrics to namespace {namespace} with dimensions {dimensions}")

# Example Usage:
if __name__ == '__main__':
    from datetime import datetime
    # Mock SNS client for example
    class MockSNSClient:
        def publish(self, TopicArn, Subject, Message, MessageStructure):
            print(f"\n--- Mock SNS Publish to {TopicArn} ---")
            print(f"Subject: {Subject}")
            print(f"Message: {Message}")
            print(f"MessageStructure: {MessageStructure}")
            return {"MessageId": "mock-message-id"}
    SNS_CLIENT = MockSNSClient()

    # Mock requests for Slack
    class MockRequests:
        def post(self, url, json, timeout):
            print(f"\n--- Mock Slack Post to {url} ---")
            print(f"Payload: {json}")
            class MockResponse:
                def raise_for_status(self):
                    pass
            return MockResponse()
    requests = MockRequests()

    sample_findings = [
        {
            "key": "1.2.3.4",
            "subkey": "/login",
            "minute": "2023-10-26T10:00",
            "value": 150,
            "score": 4.5,
            "baseline_mean": 20.0,
            "baseline_std": 5.0,
            "metric": "requests",
            "mode": "high",
            "ioc_matches": ["CIDR:1.2.3.0/24"]
        },
        {
            "key": "5.6.7.8",
            "subkey": "N/A",
            "minute": "2023-10-26T10:00",
            "value": 500,
            "score": 3.2,
            "baseline_mean": 100.0,
            "baseline_std": 10.0,
            "metric": "connections",
            "mode": "high"
        }
    ]
    sample_context = {
        "timestamp": datetime.utcnow().isoformat(),
        "source": "DetectorFunction",
        "lambda_request_id": "abc-123"
    }

    # Test SNS
    publish_sns("arn:aws:sns:us-east-1:123456789012:test-topic", sample_findings, sample_context)

    # Test Slack
    send_slack_notification("YOUR_SLACK_WEBHOOK_URL", sample_findings, sample_context)

    # Test EMF
    emf_dimensions = {"Detector": "FlowWAF", "MetricType": "Anomaly"}
    emf_metrics = {"AnomalyCount": len(sample_findings), "MaxAnomalyScore": max(abs(f['score']) for f in sample_findings)}
    emit_emf("FlowWAFSentinel", emf_dimensions, emf_metrics)