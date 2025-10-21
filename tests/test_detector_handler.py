import unittest
from unittest.mock import patch, MagicMock, call
import json
import os
import pandas as pd
from datetime import datetime, timedelta

# Mock environment variables before importing detector_handler
os.environ["ATHENA_DATABASE"] = "mock_db"
os.environ["ATHENA_WORKGROUP"] = "mock_wg"
os.environ["ATHENA_OUTPUT_LOCATION"] = "s3://mock-athena-results/"
os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:mock-topic"
os.environ["BASELINE_BUCKET"] = "mock-baseline-bucket"
os.environ["LOOKBACK_MINUTES"] = "15"
os.environ["TRAIN_DAYS"] = "7"
os.environ["EWMA_ALPHA"] = "0.3"
os.environ["SIGMA"] = "3.0"
os.environ["TOP_K"] = "5"
os.environ["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/services/mock/webhook"
os.environ["LOG_LEVEL"] = "INFO"

# Import the handler after setting environment variables
from backend.lambdas import detector_handler

class TestDetectorHandler(unittest.TestCase):

    def setUp(self):
        # Reset mocks before each test
        self.mock_boto3_client = MagicMock()
        self.mock_s3_client = MagicMock()
        self.mock_athena_client = MagicMock()
        self.mock_sns_client = MagicMock()
        self.mock_requests_post = MagicMock()

        # Patch boto3.client to return our mock clients
        patcher_boto3_client = patch('boto3.client', side_effect=self._mock_boto3_client_factory)
        self.mock_boto3_client_patch = patcher_boto3_client.start()
        self.addCleanup(patcher_boto3_client.stop)

        # Patch requests.post for Slack notifications
        patcher_requests_post = patch('requests.post', new=self.mock_requests_post)
        self.mock_requests_post_patch = patcher_requests_post.start()
        self.addCleanup(patcher_requests_post.stop)

        # Mock the _read_sql_query function to return predefined SQL
        patcher_read_sql = patch('backend.lambdas.detector_handler._read_sql_query', side_effect=self._mock_read_sql_query)
        self.mock_read_sql_patch = patcher_read_sql.start()
        self.addCleanup(patcher_read_sql.stop)

        # Mock storage.get_baseline and storage.put_baseline
        patcher_get_baseline = patch('backend.analytics.storage.get_baseline', return_value=None)
        self.mock_get_baseline_patch = patcher_get_baseline.start()
        self.addCleanup(patcher_get_baseline.stop)

        patcher_put_baseline = patch('backend.analytics.storage.put_baseline')
        self.mock_put_baseline_patch = patcher_put_baseline.start()
        self.addCleanup(patcher_put_baseline.stop)

        # Mock IOCMatcher to always return no matches for simplicity in this test
        patcher_ioc_matcher = patch('backend.analytics.ioc.IOCMatcher.match', return_value={"matched": False, "rules": []})
        self.mock_ioc_matcher_patch = patcher_ioc_matcher.start()
        self.addCleanup(patcher_ioc_matcher.stop)
        
        # Re-initialize APP_CONFIG and IOC_MATCHER in detector_handler after patching
        detector_handler.APP_CONFIG = detector_handler.config.get_config()
        detector_handler.IOC_MATCHER = detector_handler.ioc.IOCMatcher({}) # Empty IOC for this test

    def _mock_boto3_client_factory(self, service_name):
        if service_name == 'athena':
            return self.mock_athena_client
        elif service_name == 's3':
            return self.mock_s3_client
        elif service_name == 'sns':
            return self.mock_sns_client
        return MagicMock() # Return a generic mock for other clients

    def _mock_read_sql_query(self, file_path):
        # Provide dummy SQL content for the union_hotspots query
        if "union_hotspots.sql" in file_path:
            return """
            SELECT
                '2023-10-26T10:00' AS minute,
                '1.1.1.1' AS key,
                '/pathA' AS subkey,
                'US' AS country,
                NULL AS rule_label,
                100 AS value,
                'request_count' AS metric,
                'WAF' AS source_type
            UNION ALL
            SELECT
                '2023-10-26T10:00' AS minute,
                '2.2.2.2' AS key,
                '80' AS subkey,
                NULL AS country,
                NULL AS rule_label,
                200 AS value,
                'connection_count' AS metric,
                'VPC' AS source_type
            """
        return "SELECT 1;" # Default for other SQL files

    def _mock_athena_query_success(self, query_execution_id):
        # Mock Athena query execution status
        self.mock_athena_client.get_query_execution.return_value = {
            'QueryExecution': {'Status': {'State': 'SUCCEEDED'}}
        }
        # Mock Athena query results
        self.mock_athena_client.get_paginator.return_value.paginate.return_value = [
            {
                'ResultSet': {
                    'ResultSetMetadata': {
                        'ColumnInfo': [
                            {'Name': 'minute', 'Type': 'VARCHAR'},
                            {'Name': 'key', 'Type': 'VARCHAR'},
                            {'Name': 'subkey', 'Type': 'VARCHAR'},
                            {'Name': 'country', 'Type': 'VARCHAR'},
                            {'Name': 'rule_label', 'Type': 'VARCHAR'},
                            {'Name': 'value', 'Type': 'INTEGER'},
                            {'Name': 'metric', 'Type': 'VARCHAR'},
                            {'Name': 'source_type', 'Type': 'VARCHAR'}
                        ]
                    },
                    'Rows': [
                        {'Data': [{'VarCharValue': 'minute'}, {'VarCharValue': 'key'}, {'VarCharValue': 'subkey'}, {'VarCharValue': 'country'}, {'VarCharValue': 'rule_label'}, {'VarCharValue': 'value'}, {'VarCharValue': 'metric'}, {'VarCharValue': 'source_type'}]}, # Header row
                        {'Data': [{'VarCharValue': '2023-10-26T10:00'}, {'VarCharValue': '1.1.1.1'}, {'VarCharValue': '/pathA'}, {'VarCharValue': 'US'}, {'VarCharValue': 'null'}, {'VarCharValue': '100'}, {'VarCharValue': 'request_count'}, {'VarCharValue': 'WAF'}]},
                        {'Data': [{'VarCharValue': '2023-10-26T10:00'}, {'VarCharValue': '2.2.2.2'}, {'VarCharValue': '80'}, {'VarCharValue': 'null'}, {'VarCharValue': 'null'}, {'VarCharValue': '200'}, {'VarCharValue': 'connection_count'}, {'VarCharValue': 'VPC'}]}
                    ]
                }
            }
        ]

    @patch('backend.analytics.ewma.detect_anomalies')
    @patch('backend.analytics.notifier.publish_sns')
    @patch('backend.analytics.notifier.send_slack_notification')
    @patch('backend.analytics.notifier.emit_emf')
    def test_handler_with_anomalies(self, mock_emit_emf, mock_send_slack_notification, mock_publish_sns, mock_detect_anomalies):
        """
        Test the handler when anomalies are detected, verifying SNS and Slack payloads.
        """
        # Mock Athena query execution
        self.mock_athena_client.start_query_execution.return_value = {'QueryExecutionId': 'test-query-id'}
        self._mock_athena_query_success('test-query-id')

        # Mock detect_anomalies to return some anomalies
        mock_detect_anomalies.return_value = [
            {
                "key": "1.1.1.1",
                "subkey": "/pathA",
                "minute": "2023-10-26T10:00",
                "value": 100,
                "score": 4.5,
                "baseline_mean": 20.0,
                "baseline_std": 5.0,
                "metric": "request_count",
                "mode": "high",
                "ioc_matches": ["CIDR:1.1.1.0/24"] # Example IOC match
            }
        ]

        # Mock Lambda context
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        # Invoke the handler
        response = detector_handler.handler({}, mock_context)

        # Assertions
        self.assertEqual(response['statusCode'], 200)
        self.assertIn("Detection cycle finished successfully.", response['body'])

        # Verify Athena calls
        self.mock_athena_client.start_query_execution.assert_called_once()
        self.mock_athena_client.get_query_execution.assert_called() # Called multiple times for polling
        self.mock_athena_client.get_paginator.assert_called_once_with('get_query_results')

        # Verify ewma.detect_anomalies call
        mock_detect_anomalies.assert_called_once()
        self.assertIsInstance(mock_detect_anomalies.call_args[0][0], list) # First arg is data_points
        self.assertEqual(mock_detect_anomalies.call_args[1]['alpha'], float(os.environ["EWMA_ALPHA"]))

        # Verify SNS notification
        mock_publish_sns.assert_called_once()
        sns_call_args, sns_call_kwargs = mock_publish_sns.call_args
        self.assertEqual(sns_call_args[0], os.environ["SNS_TOPIC_ARN"]) # topic_arn
        self.assertEqual(len(sns_call_args[1]), 1) # findings list
        self.assertIn("Flow+WAF Anomaly Detected", sns_call_args[1][0]['subject']) # Check subject in findings

        # Verify Slack notification
        mock_send_slack_notification.assert_called_once()
        slack_call_args, slack_call_kwargs = mock_send_slack_notification.call_args
        self.assertEqual(slack_call_args[0], os.environ["SLACK_WEBHOOK_URL"]) # webhook_url
        self.assertEqual(len(slack_call_args[1]), 1) # findings list

        # Verify EMF metrics
        mock_emit_emf.assert_called_once()
        emf_call_args, emf_call_kwargs = mock_emit_emf.call_args
        self.assertEqual(emf_call_args[0], "FlowWAFSentinel") # namespace
        self.assertIn("AnomalyCount", emf_call_args[2]) # metrics dict
        self.assertEqual(emf_call_args[2]["AnomalyCount"], 1)

        # Verify baseline update (implicitly called by ewma.detect_anomalies)
        self.mock_put_baseline_patch.assert_called()

    @patch('backend.analytics.ewma.detect_anomalies', return_value=[])
    @patch('backend.analytics.notifier.publish_sns')
    @patch('backend.analytics.notifier.send_slack_notification')
    @patch('backend.analytics.notifier.emit_emf')
    def test_handler_no_anomalies(self, mock_emit_emf, mock_send_slack_notification, mock_publish_sns, mock_detect_anomalies):
        """
        Test the handler when no anomalies are detected.
        """
        self_mock_athena_query_success('test-query-id') # Ensure Athena returns data
        self.mock_athena_client.start_query_execution.return_value = {'QueryExecutionId': 'test-query-id'}
        self._mock_athena_query_success('test-query-id')

        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        response = detector_handler.handler({}, mock_context)

        self.assertEqual(response['statusCode'], 200)
        self.assertIn("No anomalies detected.", response['body'])

        mock_publish_sns.assert_not_called()
        mock_send_slack_notification.assert_not_called()
        mock_emit_emf.assert_not_called()
        self.mock_put_baseline_patch.assert_called() # Baseline should still be updated

    def test_handler_warmup_event(self):
        """Test handler with a warmup event."""
        response = detector_handler.handler({"source": "lambda.warmer"}, MagicMock())
        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(response['body'], '"Warmed up!"' )
        self.mock_athena_client.start_query_execution.assert_not_called() # No Athena calls for warmup

    @patch('backend.lambdas.detector_handler.execute_athena_query', side_effect=Exception("Athena error"))
    @patch('boto3.client') # Patch boto3.client again for error SNS
    def test_handler_athena_error(self, mock_boto3_client_for_error_sns, mock_execute_athena_query):
        """
        Test handler when Athena query fails.
        """
        # Mock SNS client for error notification
        mock_sns_client_error = MagicMock()
        mock_boto3_client_for_error_sns.return_value = mock_sns_client_error

        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        with self.assertRaisesRegex(Exception, "Athena error"):
            detector_handler.handler({}, mock_context)
        
        # Verify error SNS notification was attempted
        mock_sns_client_error.publish.assert_called_once()
        sns_call_args, sns_call_kwargs = mock_sns_client_error.publish.call_args
        self.assertIn("Flow+WAF Anomaly Detector Error", sns_call_kwargs['Subject'])
        message_payload = json.loads(sns_call_kwargs['Message'])
        self.assertIn("Athena error", message_payload['error'])

if __name__ == '__main__':
    unittest.main()