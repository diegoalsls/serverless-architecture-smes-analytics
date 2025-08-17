locals {
  bucket_list = [
    var.buckets.bronze,
    var.buckets.silver,
    var.buckets.gold,
    var.buckets.predictive
  ]
}

# -------------------------
# Buckets base
# -------------------------
resource "aws_s3_bucket" "b" {
  for_each = toset(local.bucket_list)
  bucket   = each.value
}

resource "aws_s3_bucket_ownership_controls" "o" {
  for_each = aws_s3_bucket.b
  bucket   = each.value.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "pab" {
  for_each                = aws_s3_bucket.b
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Encripción por defecto con tu CMK (recomendado)
resource "aws_s3_bucket_server_side_encryption_configuration" "sse" {
  for_each = aws_s3_bucket.b
  bucket   = each.value.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.kms_key_arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# ---------------------------------------------------------
# Bucket policy SOLO para GOLD, sin Principal="*"
# (ajusta/duplica si quieres políticas similares para otros)
# ---------------------------------------------------------
data "aws_iam_policy_document" "policy_gold" {
  # Permite a los roles de Lambda y Glue listar y leer/escribir en el bucket GOLD
  statement {
    sid = "AllowGlueAndLambdaListAndRW"
    actions = [
      "s3:ListBucket"
    ]
    resources = ["arn:aws:s3:::${var.buckets.gold}"]
    principals {
      type        = "AWS"
      identifiers = [var.glue_role_arn, var.lambda_role_arn]
    }
  }

  statement {
    sid = "AllowGlueAndLambdaGetPut"
    actions = [
      "s3:GetObject",
      "s3:PutObject"
    ]
    resources = ["arn:aws:s3:::${var.buckets.gold}/*"]
    principals {
      type        = "AWS"
      identifiers = [var.glue_role_arn, var.lambda_role_arn]
    }
  }

  # Fuerza que los PUTs que hagan esos roles usen SSE-KMS
  statement {
    sid       = "RequireKmsSSEForPutObject"
    actions   = ["s3:PutObject"]
    resources = ["arn:aws:s3:::${var.buckets.gold}/*"]
    principals {
      type        = "AWS"
      identifiers = [var.glue_role_arn, var.lambda_role_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["aws:kms"]
    }
    # Si quieres obligar TU CMK específica (además de aws:kms), descomenta:
    # condition {
    #   test     = "StringEquals"
    #   variable = "s3:x-amz-server-side-encryption-aws-kms-key-id"
    #   values   = [var.kms_key_arn]
    # }
  }
}

resource "aws_s3_bucket_policy" "gold" {
  bucket = aws_s3_bucket.b[var.buckets.gold].id
  policy = data.aws_iam_policy_document.policy_gold.json
}
