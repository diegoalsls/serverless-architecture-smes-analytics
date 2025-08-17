# LambdaExecutionRole
data "aws_iam_policy_document" "assume_lambda" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.project_prefix}${var.name_suffix}-lambda-exec"
  assume_role_policy = data.aws_iam_policy_document.assume_lambda.json
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "lambda_extra" {
  statement {
    actions   = ["s3:*"]
    resources = ["*"]
  }
  statement {
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
    resources = [var.kms_key_arn]
  }
  statement {
    actions   = ["glue:*", "athena:*", "logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "lambda_extra" {
  name   = "${var.project_prefix}${var.name_suffix}-lambda-extra"
  policy = data.aws_iam_policy_document.lambda_extra.json
}

resource "aws_iam_role_policy_attachment" "lambda_extra_attach" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.lambda_extra.arn
}

# Glue role
data "aws_iam_policy_document" "assume_glue" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "glue_job" {
  name               = "${var.project_prefix}${var.name_suffix}-glue-job"
  assume_role_policy = data.aws_iam_policy_document.assume_glue.json
}

# ✅ AQUÍ estaba el problema: todos los "statement" deben ir en bloque multilínea
data "aws_iam_policy_document" "glue_job" {
  statement {
    actions   = ["s3:*"]
    resources = ["*"]
  }
  statement {
    actions   = ["kms:*"]
    resources = [var.kms_key_arn]
  }
  statement {
    actions   = ["logs:*", "cloudwatch:*"]
    resources = ["*"]
  }
  statement {
    actions   = ["iam:PassRole"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "glue_job" {
  name   = "${var.project_prefix}${var.name_suffix}-glue-job"
  policy = data.aws_iam_policy_document.glue_job.json
}

resource "aws_iam_role_policy_attachment" "glue_job_attach" {
  role       = aws_iam_role.glue_job.name
  policy_arn = aws_iam_policy.glue_job.arn
}

# Events -> Step
data "aws_iam_policy_document" "assume_events" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "events_to_step" {
  name               = "${var.project_prefix}${var.name_suffix}-events-to-step"
  assume_role_policy = data.aws_iam_policy_document.assume_events.json
}

data "aws_iam_policy_document" "events_to_step" {
  statement {
    actions   = ["states:StartExecution"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "events_to_step" {
  name   = "${var.project_prefix}${var.name_suffix}-events-to-step"
  policy = data.aws_iam_policy_document.events_to_step.json
}

resource "aws_iam_role_policy_attachment" "events_to_step_attach" {
  role       = aws_iam_role.events_to_step.name
  policy_arn = aws_iam_policy.events_to_step.arn
}

output "lambda_role_arn" { value = aws_iam_role.lambda.arn }
output "glue_job_role_arn" { value = aws_iam_role.glue_job.arn }
output "eventbridge_to_step_role_arn" { value = aws_iam_role.events_to_step.arn }
