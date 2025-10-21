import json
import os
import requests

# TODO:
# - Improve message formatting to be more human-readable.
# - Add support for different levels of severity.
# - Consider using Jinja2 for templating complex messages.

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

def format_message(anomalies: list, ioc_matches: list) -> dict:
    """Formats the findings into a structured message for SNS."""
    # TODO: Create a more detailed and readable message body.
    subject = f"Security Anomaly Detected: {len(anomalies)} statistical anomalies, {len(ioc_matches)} IOC matches"
    
    body = "== Anomaly Detection Report ==\n\n"
    
    if anomalies:
        body += "--- Statistical Anomalies (EWMA) ---\n"
        for anomaly in anomalies:
            body += f"- Metric: {anomaly.get('metric')}, Value: {anomaly.get('value')}, Sigma: {anomaly.get('sigma')}, IP: {anomaly.get('ip')}\n"
        body += "\n"

    if ioc_matches:
        body += "--- IOC Matches ---\n"
        for match in ioc_matches:
            body += f"- IP: {match.get('ip')}, Matched on: {match.get('type')}, Value: {match.get('value')}\n"
        body += "\n"

    return {
        "subject": subject,
        "body": body,
        "anomalies": anomalies,
        "ioc_matches": ioc_matches
    }

def send_sns_notification(sns_client, topic_arn: str, message: dict):
    """Publishes the detection results to an SNS topic."""
    print(f"Sending notification to SNS topic: {topic_arn}")
    try:
        sns_client.publish(
            TopicArn=topic_arn,
            Subject=message["subject"],
            Message=json.dumps(message, indent=2),
            MessageStructure='string' # 'json' requires subscription confirmation
        )
    except Exception as e:
        print(f"Failed to publish to SNS: {e}")
        raise

def send_slack_notification(webhook_url: str, message: dict):
    """(Optional) Sends the detection results to a Slack channel."""
    if not webhook_url:
        return # Silently ignore if not configured

    print("Sending notification to Slack.")
    # TODO: Format a better Slack message (e.g., using blocks)
    slack_payload = {
        "text": message["subject"],
        "attachments": [
            {
                "color": "#f2c744",
                "text": message["body"]
            }
        ]
    }
    try:
        response = requests.post(webhook_url, json=slack_payload, timeout=5)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Slack notification: {e}")
