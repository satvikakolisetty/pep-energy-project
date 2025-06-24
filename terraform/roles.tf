# defines all IAM Roles and Policies.
# granting each service only the specific permissions required to perform its function.

data "aws_iam_policy_document" "lambda_assume_role_policy" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# First Lambda function
# Data Simulator Lambda
# This Lambda is needed to write logs and drop files into S3.
resource "aws_iam_role" "simulator_lambda_role" {
  name = "${var.project_name}-simulator-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role_policy.json
  tags = {
    Project = var.project_name
  }
}

data "aws_iam_policy_document" "simulator_lambda_policy_doc" {
  # logging permissions for debugging.
  statement {
    effect    = "Allow"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:*"]
  }
  # And the permission to upload files to specific S3 bucket.
  statement {
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.data_bucket.arn}/*"]
  }
}

resource "aws_iam_policy" "simulator_lambda_policy" {
  name        = "${var.project_name}-simulator-lambda-policy"
  description = "Allows Lambda to write logs and upload files to S3."
  policy = data.aws_iam_policy_document.simulator_lambda_policy_doc.json
}

# attach the policy to the role.
resource "aws_iam_role_policy_attachment" "simulator_lambda_attachment" {
  role       = aws_iam_role.simulator_lambda_role.name
  policy_arn = aws_iam_policy.simulator_lambda_policy.arn
}

# Second Lambda function
# Lambda for Data Processing
resource "aws_iam_role" "processor_lambda_role" {
  name = "${var.project_name}-processor-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role_policy.json
  tags = {
    Project = var.project_name
  }
}

data "aws_iam_policy_document" "processor_lambda_policy_doc" {
  statement {
    effect    = "Allow"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:*"]
  }
  # Permission to get the newly uploaded file from S3.
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.data_bucket.arn}/*"]
  }
  # Permission to write the processed data into our DynamoDB table.
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:PutItem", "dynamodb:BatchWriteItem"]
    resources = [aws_dynamodb_table.energy_data_table.arn]
  }
  # Permission to publish an alert to our SNS topic if it finds an anomaly.
  statement {
    effect    = "Allow"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.anomaly_alerts.arn]
  }
  # And permission to send a message to our Dead Letter Queue if something goes wrong.
  statement {
    effect    = "Allow"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.processing_dlq.arn]
  }
}

resource "aws_iam_policy" "processor_lambda_policy" {
  name        = "${var.project_name}-processor-lambda-policy"
  description = "Allows Lambda to read from S3, write to DynamoDB,SNS and SQS, and log."
  policy = data.aws_iam_policy_document.processor_lambda_policy_doc.json
}

resource "aws_iam_role_policy_attachment" "processor_lambda_attachment" {
  role       = aws_iam_role.processor_lambda_role.name
  policy_arn = aws_iam_policy.processor_lambda_policy.arn
}

# Third Lambda function
# Lambda for handling API 
# This lambda serves API, so its main job is to read data from the database.
resource "aws_iam_role" "api_lambda_role" {
  name = "${var.project_name}-api-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role_policy.json
  tags = {
    Project = var.project_name
  }
}

data "aws_iam_policy_document" "api_lambda_policy_doc" {
  statement {
    effect    = "Allow"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:*"]
  }
  # # allows reading from DynamoDB table.
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:Query", "dynamodb:Scan"]
    resources = [aws_dynamodb_table.energy_data_table.arn]
  }
}

resource "aws_iam_policy" "api_lambda_policy" {
  name        = "${var.project_name}-api-lambda-policy"
  description = "Allows Lambda to query DynamoDB for the API."

  policy = data.aws_iam_policy_document.api_lambda_policy_doc.json
}

resource "aws_iam_role_policy_attachment" "api_lambda_attachment" {
  role       = aws_iam_role.api_lambda_role.name
  policy_arn = aws_iam_policy.api_lambda_policy.arn
}