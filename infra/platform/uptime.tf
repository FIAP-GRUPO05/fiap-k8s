variable "api_endpoints" {
  type = map(string)
  default = {
    develop = "https://szjrcgb6vj.execute-api.sa-east-1.amazonaws.com"
    homol   = "https://3n6qyl3n18.execute-api.sa-east-1.amazonaws.com"
    prod    = "https://rf4lntvt1f.execute-api.sa-east-1.amazonaws.com"
  }
  description = "Fixed public API Gateway endpoints for external HTTPS health and JWKS checks."
}

data "archive_file" "uptime" {
  type        = "zip"
  source_file = "${path.module}/scripts/check_uptime.py"
  output_path = "${path.module}/uptime.zip"
}

resource "aws_cloudwatch_log_group" "uptime" {
  name              = "/aws/lambda/fiap-uptime-probe"
  retention_in_days = 14
}

resource "aws_iam_role" "uptime" {
  name = "fiap-uptime-probe"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "uptime" {
  name = "fiap-uptime-probe"
  role = aws_iam_role.uptime.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = aws_secretsmanager_secret.newrelic.arn },
      { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.uptime.arn}:*" }
    ]
  })
}

resource "aws_lambda_function" "uptime" {
  function_name    = "fiap-uptime-probe"
  description      = "External HTTPS health and JWKS checks reported to New Relic every five minutes"
  role             = aws_iam_role.uptime.arn
  runtime          = "python3.12"
  handler          = "check_uptime.lambda_handler"
  memory_size      = 128
  timeout          = 90
  filename         = data.archive_file.uptime.output_path
  source_code_hash = data.archive_file.uptime.output_base64sha256
  environment {
    variables = { NEW_RELIC_SECRET_ARN = aws_secretsmanager_secret.newrelic.arn, API_ENDPOINTS = jsonencode(var.api_endpoints) }
  }
  depends_on = [aws_iam_role_policy.uptime]
}

resource "aws_cloudwatch_event_rule" "uptime" {
  name                = "fiap-uptime-every-five-minutes"
  description         = "Check all three public FIAP environments"
  schedule_expression = "rate(5 minutes)"
}

resource "aws_cloudwatch_event_target" "uptime" {
  rule      = aws_cloudwatch_event_rule.uptime.name
  target_id = "fiap-uptime-probe"
  arn       = aws_lambda_function.uptime.arn
  retry_policy {
    maximum_retry_attempts       = 1
    maximum_event_age_in_seconds = 120
  }
}

resource "aws_lambda_permission" "uptime_schedule" {
  statement_id  = "AllowScheduledUptime"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uptime.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.uptime.arn
}
