resource "aws_cloudwatch_event_rule" "rule" {
  name                = "etl-schedule${var.name_suffix}"
  schedule_expression = var.schedule_expression
}
resource "aws_cloudwatch_event_target" "target" {
  rule      = aws_cloudwatch_event_rule.rule.name
  target_id = "run-sm${var.name_suffix}"
  arn       = var.target_arn
  role_arn  = var.invoke_role_arn
}
