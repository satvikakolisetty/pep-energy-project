# defines the output values from tf deployment.

output "s3_bucket_name" {
  description = "The name of the S3 bucket for raw data."
  value       = aws_s3_bucket.data_bucket.bucket
}

output "dynamodb_table_name" {
  description = "The name of the DynamoDB table for processed data."
  value       = aws_dynamodb_table.energy_data_table.name
}

output "api_endpoint_url" {
  description = "The public base URL for the deployed API."
  value       = aws_api_gateway_stage.api_stage.invoke_url
}

output "sns_topic_arn" {
  description = "The ARN of the SNS topic for anomaly alerts."
  value       = aws_sns_topic.anomaly_alerts.arn
}
