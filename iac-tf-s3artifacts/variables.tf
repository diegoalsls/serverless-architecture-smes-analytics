variable "region" {
  type = string
}

variable "account_id" {
  type = string
}

variable "project_prefix" {
  type = string
}

variable "allowed_ip_cidr" {
  type = string
}

variable "name_suffix" {
  type    = string
  default = "0"
}

variable "code_root" {
  type    = string
  default = "./code"
}

# Buckets EXACTOS (sin sufijo); el sufijo se aplica en módulos
variable "buckets" {
  type = object({
    bronze     = string # ej: serverless-architecture-smes-analytics-bronze-zone
    silver     = string # ej: serverless-architecture-smes-analytics-silver-zone
    gold       = string # ej: serverless-architecture-smes-analytics-gold-zone
    predictive = string # ej: serverless-architecture-smes-analytics-predictive
  })
}

# Lambdas: carpetas/código o (en tu variante s3artifacts) mapa con bucket/key/props
# Para el paquete que estás usando (s3artifacts), esta variable NO se usa.
variable "lambda_sources" {
  description = "Mapa de lambdas si se empaquetan localmente"
  type = map(object({
    source_dir = string
    handler    = string
    runtime    = string
    timeout    = number
    memory     = number
    env        = map(string)
  }))
  default = {}
}

# Para artefactos S3 (paquete s3artifacts): bucket + key de cada lambda
variable "artifact_bucket" {
  type = string
}

variable "lambda_packages" {
  description = "Key lógico -> { s3_key, handler, runtime, timeout, memory, env }"
  type = map(object({
    s3_key  = string
    handler = string
    runtime = string
    timeout = number
    memory  = number
    env     = map(string)
  }))
}

# Glue: nombre de DB
variable "glue_database_name" {
  type    = string
  default = "gold_analytics"
}

# Glue: scripts locales (cuando aplica). Para s3artifacts usamos directamente s3_uri.
variable "glue_scripts" {
  description = "Mapa de scripts Glue locales (no usado en s3artifacts)"
  type = map(object({
    file     = string
    dest_key = string
  }))
  default = {}
}

# Glue: scripts en S3 (lo que estás usando)
variable "glue_scripts_s3" {
  description = "Mapa de scripts Glue ubicados ya en S3: nombre -> { s3_uri }"
  type = map(object({
    s3_uri = string
  }))
  default = {}
}

variable "glue_classifiers" {
  type = map(object({
    name      = string
    type      = string # "csv"
    delimiter = string
    quote     = optional(string)
    header    = optional(bool)
  }))
  default = {}
}

variable "glue_crawlers" {
  type = map(object({
    name       = string
    s3_targets = list(string)
    schedule   = optional(string)
  }))
  default = {}
}

variable "glue_jobs" {
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
  default = {}
}

# Step Functions
variable "step_definition_vars" {
  type    = map(string)
  default = {}
}

# EventBridge
variable "schedule_expression" {
  type    = string
  default = "rate(1 day)"
}
