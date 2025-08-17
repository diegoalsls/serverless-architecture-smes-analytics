resource "aws_lambda_function" "fn" {
  for_each = var.lambda_packages

  function_name = "${each.key}${var.name_suffix}"
  role          = var.role_arn
  s3_bucket     = var.artifact_bucket
  s3_key        = each.value.s3_key
  handler       = each.value.handler
  runtime       = each.value.runtime
  timeout       = each.value.timeout
  memory_size   = each.value.memory
  kms_key_arn   = var.kms_key_arn

  environment { variables = each.value.env }
}

output "lambda_arns" { value = { for k, v in aws_lambda_function.fn : k => v.arn } }
