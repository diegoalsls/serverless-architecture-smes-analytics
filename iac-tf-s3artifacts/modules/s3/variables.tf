variable "buckets" {
  type = object({
    bronze     = string
    silver     = string
    gold       = string
    predictive = string
  })
}
variable "allowed_ip_cidr" { type = string }
variable "lambda_role_arn" { type = string }
variable "glue_role_arn" { type = string }
variable "kms_key_arn" { type = string }
