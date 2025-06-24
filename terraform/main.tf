# This file defines the AWS resources for the data pipeline.

provider "aws" {
  region = var.aws_region
}

#1. Data Ingestion and Storage
# S3 bucket for storing raw incoming JSON data files.
resource "aws_s3_bucket" "data_bucket" {
  bucket = "${var.project_name}-raw-data-bucket-${random_id.bucket_id.hex}"
  force_destroy = true
  tags = {
    Project = var.project_name
  }
}
# Provides a random suffix to make sure that S3 bucket name is unique.
resource "random_id" "bucket_id" {
  byte_length = 8
}

# DynamoDB table for storing processed energy data.
resource "aws_dynamodb_table" "energy_data_table" {
  name           = "${var.project_name}-EnergyDataTable"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "site_id"
  range_key      = "timestamp"
  # Partition Key
  attribute {
    name = "site_id"
    type = "S" 
  }
  # Sort Key
  attribute {
    name = "timestamp"
    type = "S" 
  }
  tags = {
    Project = var.project_name
  }
}

# 2.Data Simulation
# Lambda function for generating mock data.
resource "aws_lambda_function" "simulator_lambda" {
  filename         = "../src/lambda_data_simulation/deploy.zip"
  function_name    = "${var.project_name}-data-simulator"
  role             = aws_iam_role.simulator_lambda_role.arn
  handler          = "handler.generate_data_handler"
  runtime          = "python3.9"
  source_code_hash = filebase64sha256("../src/lambda_data_simulation/deploy.zip")
  environment {
    variables = {
      S3_BUCKET_NAME = aws_s3_bucket.data_bucket.bucket
    }
  }
  tags = {
    Project = var.project_name
  }
}

# EventBridge rule to trigger the simulator Lambda for every 5 minutes.
resource "aws_cloudwatch_event_rule" "every_five_minutes" {
  name                = "${var.project_name}-every-five-minutes"
  description         = "Triggers the data simulator Lambda every 5 minutes."
  schedule_expression = "rate(5 minutes)"
  tags = {
    Project = var.project_name
  }
}

# Connects the EventBridge rule to the simulator Lambda function.
resource "aws_cloudwatch_event_target" "trigger_simulator_lambda" {
  rule      = aws_cloudwatch_event_rule.every_five_minutes.name
  target_id = "TriggerSimulatorLambda"
  arn       = aws_lambda_function.simulator_lambda.arn
}

# Gives EventBridge permission to invoke the simulator Lambda function.
resource "aws_lambda_permission" "allow_cloudwatch_to_call_simulator" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.simulator_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.every_five_minutes.arn
}


# 3.Data Processing
# Lambda function to process raw data files from S3 bucket.
resource "aws_lambda_function" "processor_lambda" {
  filename         = "../src/lambda_data_processing/deploy.zip"
  function_name    = "${var.project_name}-data-processor"
  role             = aws_iam_role.processor_lambda_role.arn
  handler          = "handler.process_s3_file_handler"
  runtime          = "python3.9"
  timeout          = 30
  source_code_hash = filebase64sha256("../src/lambda_data_processing/deploy.zip")
  environment {
    variables = {
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.energy_data_table.name
      SNS_TOPIC_ARN       = aws_sns_topic.anomaly_alerts.arn
    }
  }
  # Configuring the Dead-Letter Queue for error handling.
  dead_letter_config {
    target_arn = aws_sqs_queue.processing_dlq.arn
  }
  tags = {
    Project = var.project_name
  }
}

# S3 bucket notification to trigger the processor Lambda on new object creation.
resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = aws_s3_bucket.data_bucket.id
  lambda_function {
    lambda_function_arn = aws_lambda_function.processor_lambda.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "raw/"
    filter_suffix       = ".json"
  }
  depends_on = [aws_lambda_permission.allow_s3_to_call_processor]
}

# Grants S3 permission to trigger the processor Lambda function.
resource "aws_lambda_permission" "allow_s3_to_call_processor" {
  statement_id  = "AllowExecutionFromS3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.processor_lambda.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.data_bucket.arn
}


# 4. Alerting and Handling errors

# SNS Topic for anomaly alerts.
resource "aws_sns_topic" "anomaly_alerts" {
  name = "${var.project_name}-anomaly-alerts"
  tags = {
    Project = var.project_name
  }
}
# Subscribes an email endpoint to the SNS topic for notifications.
resource "aws_sns_topic_subscription" "email_target" {
  topic_arn = aws_sns_topic.anomaly_alerts.arn
  protocol  = "email"
  endpoint  = "sathvika.kolisetty09@gmail.com"
}
# SQS queue as a Dead-Letter Queue for failed Lambda invocations.
resource "aws_sqs_queue" "processing_dlq" {
  name = "${var.project_name}-processing-dlq"
  tags = {
    Project = var.project_name
  }
}

# 5. API Layer (API Gateway + Lambda)

# Lambda function with FastAPI.
resource "aws_lambda_function" "api_lambda" {
  filename         = "../src/lambda_api/deploy.zip"
  function_name    = "${var.project_name}-api-handler"
  role             = aws_iam_role.api_lambda_role.arn
  handler          = "handler.handler"
  runtime          = "python3.9"
  timeout          = 30
  source_code_hash = filebase64sha256("../src/lambda_api/deploy.zip")
  environment {
    variables = {
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.energy_data_table.name
      # Pass the stage name to the Lambda so FastAPI knows its root path.
      API_STAGE_NAME      = aws_api_gateway_stage.api_stage.stage_name
    }
  }
  tags = {
    Project = var.project_name
  }
}

# API Gateway REST API - the front door for our service.
resource "aws_api_gateway_rest_api" "api" {
  name        = "${var.project_name}-EnergyApi"
  description = "API gateway"
}

# proxy to forward all requests to the Lambda function.
# FastAPI handles all the routings internally.
resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "proxy_method" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = "NONE"
}

# Integration between the ANY {proxy+} method and the API Lambda function.
resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_method.proxy_method.resource_id
  http_method             = aws_api_gateway_method.proxy_method.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api_lambda.invoke_arn
}

resource "aws_api_gateway_method" "proxy_root" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_rest_api.api.root_resource_id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda_root_integration" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_method.proxy_root.resource_id
  http_method             = aws_api_gateway_method.proxy_root.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api_lambda.invoke_arn
}

# deployment resource for the API Gateway.
resource "aws_api_gateway_deployment" "api_deployment" {
  rest_api_id = aws_api_gateway_rest_api.api.id

  # This trigger makes sure that new deployment is created when the API structure changes.
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.proxy.id,
      aws_api_gateway_method.proxy_method.id,
      aws_api_gateway_integration.lambda_integration.id,
      aws_api_gateway_method.proxy_root.id,
      aws_api_gateway_integration.lambda_root_integration.id,
    ]))
  }

  # This block prevents downtime during updates.
  lifecycle {
    create_before_destroy = true
  }
}

# production stage for the deployment
resource "aws_api_gateway_stage" "api_stage" {
  deployment_id = aws_api_gateway_deployment.api_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
  stage_name    = "prod"
  tags = {
    Project = var.project_name
  }
}

# giving API Gateway permission to invoke the API handler Lambda function.
resource "aws_lambda_permission" "allow_apigateway_to_call_api" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}