variable "glue_role_arn" { type = string }
variable "buckets" {
  type = object({
    bronze     = string
    silver     = string
    gold       = string
    predictive = string
  })
}
variable "kms_key_arn" { type = string }
variable "name_suffix" { type = string }

variable "database_name" { type = string }
variable "classifiers" {
  type = map(object({
    name      = string
    type      = string
    delimiter = string
    quote     = optional(string)
    header    = optional(bool)
  }))
}
variable "crawlers" {
  type = map(object({
    name       = string
    s3_targets = list(string)
    schedule   = optional(string)
  }))
}
variable "jobs" {
  type = map(object({
    name           = string
    script_s3      = string
    glue_version   = optional(string, "4.0")
    worker_type    = optional(string, "G.1X")
    number_workers = optional(number, 2)
    max_retries    = optional(number, 0)
    timeout        = optional(number, 10)
    default_args   = optional(map(string), {})
  }))
}
