# IAC Terraform (artefactos en S3)

- El código de **Lambda** y **Glue** se consume **directamente** de:
  - s3://serverless-architecture-smes-analytics-deploy/PyLambda/
  - s3://serverless-architecture-smes-analytics-deploy/PyGlue/
- El proyecto Terraform puedes guardarlo en:
  - s3://serverless-architecture-smes-analytics-deploy/iac-tf/  (para referencia)  
  y ejecutarlo localmente desde tu máquina/CI con estos archivos.

## Despliegue
```
terraform init
terraform plan -var-file=env.tfvars -out=tfplan
terraform apply tfplan
```
