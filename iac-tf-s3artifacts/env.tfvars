region          = "us-east-1"
account_id      = "302772524387"
project_prefix  = "serverless-architecture-smes-analytics"
allowed_ip_cidr = "152.203.107.202/32"
name_suffix     = "0"

# Nombres base sin sufijo
buckets = {
  bronze     = "serverless-architecture-smes-analytics-bronze-zone"
  silver     = "serverless-architecture-smes-analytics-silver-zone"
  gold       = "serverless-architecture-smes-analytics-gold-zone"
  predictive = "serverless-architecture-smes-analytics-predictive"
}

# Artefactos existentes en S3 (mismo bucket donde guardas iac-tf/)
artifact_bucket = "serverless-architecture-smes-analytics-deploy"

lambda_packages = {
  glue_tables = {
    s3_key  = "PyLambda/lambda_function_glue_tables.zip"
    handler = "lambda_function.lambda_handler"
    runtime = "python3.12"
    timeout = 300
    memory  = 1024
    env = {
      BUCKET = "serverless-architecture-smes-analytics-gold-zone0"
    }
  }
  quality = {
    s3_key  = "PyLambda/lambda_function_quality.zip"
    handler = "lambda_function.lambda_handler"
    runtime = "python3.12"
    timeout = 300
    memory  = 1024
    env = {
      BUCKET = "serverless-architecture-smes-analytics-silver-zone0"
    }
  }
  transform = {
    s3_key  = "PyLambda/lambda_function_transform.zip"
    handler = "lambda_function.lambda_handler"
    runtime = "python3.12"
    timeout = 900
    memory  = 2048
    env = {
      BUCKET = "serverless-architecture-smes-analytics-bronze-zone0"
    }
  }
}

# Scripts Glue ya existentes en S3
glue_scripts_s3 = {
  prediction_pacientes = {
    s3_uri = "s3://serverless-architecture-smes-analytics-deploy/PyGlue/glue_prediction_pacientes.py"
  }
}

glue_database_name = "gold_analytics"

glue_classifiers = {
  csv_semicolon = { name = "csv_semicolon", type = "csv", delimiter = ";" }
}

# Ejemplos de crawlers (ajusta rutas S3 reales)
glue_crawlers = {
  pacientes = {
    name       = "pacientes"
    s3_targets = ["s3://serverless-architecture-smes-analytics-gold-zone0/pacientes/"]
  }
}

# Job que usa el script en PyGlue
glue_jobs = {
  predictive_logreg = {
    name           = "predictive_logreg"
    script_s3      = "s3://serverless-architecture-smes-analytics-deploy/PyGlue/glue_prediction_pacientes.py"
    glue_version   = "4.0"
    worker_type    = "G.1X"
    number_workers = 2
    timeout        = 20
    default_args   = { "--job-language" = "python" }
  }
}

# Step Functions: de ejemplo, invoca quality0; puedes cambiar a otra Lambda
step_definition_vars = {
  prediction_lambda_arn = "" # Opcional: luego de apply puedes actualizarlo a module.lambdas.lambda_arns["quality"]
}

schedule_expression = "rate(1 day)"
