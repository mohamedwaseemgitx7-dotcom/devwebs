# FlashCart API on Lambda (Mangum) behind a Function URL. The URL is public at the network level but the app
# rejects any request without CloudFront's secret X-Origin-Verify header (OriginVerifyMiddleware).

resource "random_password" "origin_verify" {
  length  = 48
  special = false
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${var.name}-api"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api" {
  name               = "${var.name}-api-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

# Least privilege: write to its own log group only. No other AWS API access.
data "aws_iam_policy_document" "api_logs" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.api.arn}:*"]
  }
}

resource "aws_iam_role_policy" "api_logs" {
  name   = "logs"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api_logs.json
}

resource "aws_lambda_function" "api" {
  function_name    = "${var.name}-api"
  role             = aws_iam_role.api.arn
  runtime          = "python3.13"
  architectures    = ["arm64"]
  handler          = "app.asgi.handler"
  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)
  memory_size      = var.lambda_memory_mb
  timeout          = 15

  reserved_concurrent_executions = var.lambda_reserved_concurrency

  logging_config {
    log_format = "Text" # the app already emits structured JSON lines
    log_group  = aws_cloudwatch_log_group.api.name
  }

  environment {
    variables = {
      FLASHCART_ENV                   = "production"
      FLASHCART_MONGODB_URI           = var.mongodb_uri
      FLASHCART_MONGODB_DB            = "flashcart"
      FLASHCART_MONGODB_MAX_POOL_SIZE = "5" # each warm Lambda holds its own pool; Atlas M0 allows 500 connections
      FLASHCART_JWT_SECRET            = var.jwt_secret
      FLASHCART_WEBHOOK_SECRET        = var.webhook_secret
      FLASHCART_METRICS_TOKEN         = var.metrics_token
      FLASHCART_ORIGIN_VERIFY_SECRET  = random_password.origin_verify.result
      FLASHCART_COOKIE_SECURE         = "true"
      FLASHCART_CORS_ORIGINS          = "[]"
    }
  }

  depends_on = [aws_iam_role_policy.api_logs]
}

resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE" # see header comment; OAC would block browser POSTs without a body hash
}
