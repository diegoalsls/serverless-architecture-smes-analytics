# modules/stepfunctions/outputs.tf
output "state_machine_arn" {
  description = "ARN de la State Machine"
  value       = aws_sfn_state_machine.sm.arn
}