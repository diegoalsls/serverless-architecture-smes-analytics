data "template_file" "def" {
  template = file("${path.module}/definition.json.tpl")
  vars     = var.definition_vars
}

# Rol de la State Machine
data "aws_iam_policy_document" "assume_sm" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sm" {
  name               = "${var.name_prefix}-sm-role"
  assume_role_policy = data.aws_iam_policy_document.assume_sm.json
}

data "aws_iam_policy_document" "sm_policy" {
  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "sm_policy" {
  name   = "${var.name_prefix}-sm-policy"
  policy = data.aws_iam_policy_document.sm_policy.json
}

resource "aws_iam_role_policy_attachment" "sm_attach" {
  role       = aws_iam_role.sm.name
  policy_arn = aws_iam_policy.sm_policy.arn
}

# 👇 Espera explícita tras adjuntar la política (subimos a 30s)
resource "time_sleep" "after_policy_attach" {
  create_duration = "30s"
  depends_on      = [aws_iam_role_policy_attachment.sm_attach]
}

# State Machine
resource "aws_sfn_state_machine" "sm" {
  name       = "${var.name_prefix}-sm"
  role_arn   = aws_iam_role.sm.arn
  definition = data.template_file.def.rendered

  encryption_configuration {
    type       = "CUSTOMER_MANAGED_KMS_KEY"
    kms_key_id = var.kms_key_arn
  }

  # 👇 Asegura que la SM se cree/actualice SOLO tras la espera
  depends_on = [time_sleep.after_policy_attach]
}
