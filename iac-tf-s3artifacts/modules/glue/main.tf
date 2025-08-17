resource "aws_glue_catalog_database" "db" {
  name = "${var.database_name}${var.name_suffix}"
}

resource "aws_glue_classifier" "csv" {
  for_each = { for k, v in var.classifiers : k => v if v.type == "csv" }

  name = "${each.value.name}${var.name_suffix}"
  csv_classifier {
    delimiter       = each.value.delimiter
    contains_header = (try(each.value.header, false) == true) ? "PRESENT" : "UNKNOWN"
    quote_symbol    = lookup(each.value, "quote", null)
  }
}

resource "aws_glue_crawler" "crawler" {
  for_each = var.crawlers

  name          = "${each.value.name}${var.name_suffix}"
  role          = var.glue_role_arn
  database_name = aws_glue_catalog_database.db.name

  # Targets S3 (puedes repetir varios bloques s3_target)
  dynamic "s3_target" {
    for_each = each.value.s3_targets
    content {
      path = s3_target.value
    }
  }

  # 👇 Aquí el cambio: 'schedule' es atributo, no bloque
  schedule = contains(keys(each.value), "schedule") ? each.value.schedule : null

  configuration = jsonencode({
    Version = 1.0
    Grouping = {
      TableLevelConfiguration = 3
    }
  })
}

resource "aws_glue_job" "job" {
  for_each = var.jobs

  name     = "${each.value.name}${var.name_suffix}"
  role_arn = var.glue_role_arn

  glue_version      = each.value.glue_version
  number_of_workers = each.value.number_workers
  worker_type       = each.value.worker_type
  max_retries       = each.value.max_retries
  timeout           = each.value.timeout

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = each.value.script_s3
  }

  default_arguments = merge({
    "--job-language"                     = "python"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-spark-ui"                  = "true"
  }, lookup(each.value, "default_args", {}))
}

output "database_name" {
  value = aws_glue_catalog_database.db.name
}
