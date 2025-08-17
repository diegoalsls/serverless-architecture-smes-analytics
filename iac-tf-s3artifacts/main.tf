locals {
  buckets_suffixed = {
    bronze     = "${var.buckets.bronze}${var.name_suffix}"
    silver     = "${var.buckets.silver}${var.name_suffix}"
    gold       = "${var.buckets.gold}${var.name_suffix}"
    predictive = "${var.buckets.predictive}${var.name_suffix}"
  }
}

module "kms" {
  source         = "./modules/kms"
  project_prefix = var.project_prefix
  name_suffix    = var.name_suffix
}

module "iam" {
  source         = "./modules/iam"
  project_prefix = var.project_prefix
  name_suffix    = var.name_suffix
  kms_key_arn    = module.kms.key_arn
}

module "s3" {
  source          = "./modules/s3"
  buckets         = local.buckets_suffixed
  allowed_ip_cidr = var.allowed_ip_cidr
  lambda_role_arn = module.iam.lambda_role_arn
  glue_role_arn   = module.iam.glue_job_role_arn
  kms_key_arn     = module.kms.key_arn
}

module "lambdas" {
  source          = "./modules/lambdas_s3"
  role_arn        = module.iam.lambda_role_arn
  kms_key_arn     = module.kms.key_arn
  name_suffix     = var.name_suffix
  artifact_bucket = var.artifact_bucket
  lambda_packages = var.lambda_packages
}

module "glue" {
  source        = "./modules/glue"
  glue_role_arn = module.iam.glue_job_role_arn
  buckets       = local.buckets_suffixed
  kms_key_arn   = module.kms.key_arn
  name_suffix   = var.name_suffix

  database_name = var.glue_database_name
  classifiers   = var.glue_classifiers
  crawlers      = var.glue_crawlers
  jobs          = var.glue_jobs
}

module "step" {
  source      = "./modules/stepfunctions"
  name_prefix = "${var.project_prefix}${var.name_suffix}-etl"

  # ARN real de la Lambda a invocar (usa la que elegiste)
  definition_vars = {
    prediction_lambda_arn = module.lambdas.lambda_arns["quality"]
  }

  kms_key_arn = module.kms.key_arn

  # 👇 AÑADE ESTO
  depends_on = [
    module.iam,
    module.lambdas
  ]
}

module "eventbridge" {
  source              = "./modules/eventbridge"
  schedule_expression = var.schedule_expression
  target_arn          = module.step.state_machine_arn
  invoke_role_arn     = module.iam.eventbridge_to_step_role_arn
  name_suffix         = var.name_suffix
}

output "bucket_names" { value = local.buckets_suffixed }
output "lambda_arns" { value = module.lambdas.lambda_arns }
output "state_machine_arn" { value = module.step.state_machine_arn }
