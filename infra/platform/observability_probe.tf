data "archive_file" "observability_probe" {
  type        = "zip"
  source_file = "${path.module}/scripts/verify_observability.py"
  output_path = "${path.module}/observability-probe.zip"
}

resource "aws_cloudwatch_log_group" "observability_probe" {
  name              = "/aws/lambda/fiap-observability-probe"
  retention_in_days = 14
}

resource "aws_iam_role" "observability_probe" {
  name = "fiap-observability-probe"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "observability_probe" {
  name = "fiap-observability-probe"
  role = aws_iam_role.observability_probe.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = aws_secretsmanager_secret.newrelic.arn },
      { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.observability_probe.arn}:*" }
    ]
  })
}

resource "aws_lambda_function" "observability_probe" {
  function_name    = "fiap-observability-probe"
  description      = "Read aggregate cluster/APM telemetry without exposing New Relic credentials"
  role             = aws_iam_role.observability_probe.arn
  runtime          = "python3.12"
  handler          = "verify_observability.lambda_handler"
  memory_size      = 128
  timeout          = 75
  filename         = data.archive_file.observability_probe.output_path
  source_code_hash = data.archive_file.observability_probe.output_base64sha256
  environment {
    variables = { NEW_RELIC_SECRET_ARN = aws_secretsmanager_secret.newrelic.arn }
  }
  depends_on = [aws_iam_role_policy.observability_probe]
}
