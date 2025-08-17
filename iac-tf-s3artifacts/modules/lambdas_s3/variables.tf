variable "artifact_bucket" { type = string }
variable "lambda_packages" {
  type = map(object({
    s3_key : string
    handler : string
    runtime : string
    timeout : number
    memory : number
    env : map(string)
  }))
}
variable "role_arn" { type = string }
variable "kms_key_arn" { type = string }
variable "name_suffix" { type = string }
