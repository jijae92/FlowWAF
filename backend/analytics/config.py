import os
from dataclasses import dataclass

@dataclass
class AppConfig:
    """Application configuration parsed from environment variables."""
    athena_database: str
    athena_workgroup: str
    athena_output_location: str
    sns_topic_arn: str
    baseline_bucket: str
    # Optional
    log_level: str = "INFO"
    slack_webhook_url: str | None = None


def get_config() -> AppConfig:
    """
    Parses and returns the application configuration from environment variables.
    """
    try:
        return AppConfig(
            athena_database=os.environ["ATHENA_DATABASE"],
            athena_workgroup=os.environ["ATHENA_WORKGROUP"],
            athena_output_location=os.environ["ATHENA_OUTPUT_LOCATION"],
            sns_topic_arn=os.environ["SNS_TOPIC_ARN"],
            baseline_bucket=os.environ["BASELINE_BUCKET"],
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL"),
        )
    except KeyError as e:
        print(f"FATAL: Missing required environment variable: {e}")
        raise
