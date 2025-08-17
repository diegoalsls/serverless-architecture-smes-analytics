resource "aws_kms_key" "main" {
  description             = "${var.project_prefix}${var.name_suffix} CMK"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}
resource "aws_kms_alias" "alias" {
  name          = "alias/${var.project_prefix}${var.name_suffix}"
  target_key_id = aws_kms_key.main.key_id
}
output "key_arn" { value = aws_kms_key.main.arn }
