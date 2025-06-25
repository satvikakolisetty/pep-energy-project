import os
import json
import boto3
import urllib.parse
from decimal import Decimal

# Fetch environment variables.
DYNAMODB_TABLE_NAME = os.environ['DYNAMODB_TABLE_NAME']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']

# Initialize AWS clients.
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
sns_client = boto3.client('sns')
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

def process_s3_file_handler(event, context):
    """
    This Lambda function is triggered by an S3 'ObjectCreated' event.
    It processes the uploaded JSON file, enriches the data, identifies anomalies,
    and stores the records in DynamoDB.
    """
    # Using a 'try...except' block is imp for error handling. If any part
    # of this process fails, we log the error, and the Lambda invocation will fail.
    # This failure will then be routed to our SQS Dead-Letter Queue.
    try:

        # to test DLQ

        #raise ValueError("Intentional failure to test the Dead-Letter Queue.")

        # Get the bucket and filename from the S3 event.
        s3_event_record = event['Records'][0]['s3']
        bucket_name = s3_event_record['bucket']['name']
        # The key can have special characters, so we unquote it.
        key = urllib.parse.unquote_plus(s3_event_record['object']['key'], encoding='utf-8')
        
        print(f"Processing file: s3://{bucket_name}/{key}")
        
        # Get the JSON file content from S3.
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        content = response['Body'].read().decode('utf-8')
        records = json.loads(content)
        
        # Use DynamoDB's batch_writer for efficient bulk writes.
        with table.batch_writer() as batch:
            for record in records:
                site_id = record['site_id']
                generated = record['energy_generated_kwh']
                consumed = record['energy_consumed_kwh']
                
                # Business logic: Calculate net energy and check for anomalies.
                net_energy = generated - consumed
                is_anomaly = bool(generated < 0 or consumed < 0)
                
                # Create the item to be stored in DynamoDB.
                # Note: We must convert floats to DynamoDB's Decimal type.
                item = {
                    'site_id': site_id,
                    'timestamp': record['timestamp'],
                    'energy_generated_kwh': Decimal(str(generated)),
                    'energy_consumed_kwh': Decimal(str(consumed)),
                    'net_energy_kwh': Decimal(str(round(net_energy, 2))),
                    'anomaly': is_anomaly
                }
                
                # Add the processed record to the batch.
                batch.put_item(Item=item)
                
                # If an anomaly is detected, publish a notification to the SNS topic.
                if is_anomaly:
                    print(f"Anomaly detected for site_id: {site_id}. Publishing to SNS..")
                    sns_client.publish(
                        TopicArn=SNS_TOPIC_ARN,
                        Subject=f"Anomaly Detected for Site: {site_id}",
                        Message=f"An anomalous energy record was detected for site '{site_id}' at {record['timestamp']}.\n\n"
                                f"Details:\n"
                                f"  - Energy Generated: {generated} kWh\n"
                                f"  - Energy Consumed: {consumed} kWh\n\n"
                                f"File: s3://{bucket_name}/{key}"
                    )
        
        print(f"Successfully processed and stored {len(records)} records.")
        return {
            'statusCode': 200,
            'body': json.dumps('File processed successfully!')
        }
        
    except Exception as e:
        print(f"Error processing file: {str(e)}")
        # raising the exception ensures the invocation is marked as failed,
        # which is necessary for the Dead-Letter Queue to receive the event.
        raise e