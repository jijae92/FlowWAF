import os
import json
import boto3

# TODO:
# - This is an optional component.
# - The primary purpose is to invoke the main detector_handler on a more frequent
#   schedule (e.g., every 1 minute) with a special 'warmup' event.
# - This keeps the Lambda container "warm" to reduce cold start latency for the
#   actual detection run.
# - The detector_handler needs to be modified to recognize and quickly exit
#   when it receives a warmup event.

print("Loading function")

LAMBDA_CLIENT = boto3.client("lambda")
FUNCTION_NAME = os.environ.get("DETECTOR_LAMBDA_NAME")

def handler(event, context):
    """
    Invokes the main detector Lambda to keep it warm.
    """
    if not FUNCTION_NAME:
        print("Error: DETECTOR_LAMBDA_NAME environment variable not set.")
        return

    print(f"Warming up function: {FUNCTION_NAME}")

    try:
        LAMBDA_CLIENT.invoke(
            FunctionName=FUNCTION_NAME,
            InvocationType="RequestResponse", # or "Event" for async
            Payload=json.dumps({"source": "lambda.warmer"}),
        )
        print(f"Successfully invoked {FUNCTION_NAME} for warmup.")
    except Exception as e:
        print(f"Error invoking lambda: {e}")
        # Fail silently, as this is a non-critical function
        pass

    return {
        'statusCode': 200,
        'body': json.dumps('Warmup complete')
    }
