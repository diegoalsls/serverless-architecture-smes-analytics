import json
import os
import time
import boto3

# ────────────── Configuración ─────────────────────────────────────────────
REGION        = "us-east-1"
DB_NAME       = "smes_analytics"
GLUE_ROLE_ARN = "arn:aws:iam::302772524387:role/glue_service_role_for_crawlers"

# Conjuntos de datos que vamos a catalogar
DATASETS = {
    "pacientes": {
        "path": "s3://serverless-architecture-smes-analytics-gold-zone/gold1/pacientes/",
        "classifiers": ["csv_semicolon"],
    },
    "procedimientos": {
        "path": "s3://serverless-architecture-smes-analytics-gold-zone/gold1/procedimientos/",
        "classifiers": ["csv_comma"],
    },
    "recomendacion_pacientes": {
        "path": "s3://serverless-architecture-smes-analytics-predictive/prediction/recomendacion_procedimientos/",
        "classifiers": ["csv_comma"],
    },
    "consolidado_procedimientos": {
        "path": "s3://serverless-architecture-smes-analytics-gold-zone/gold1/mensual_proc/",
        "classifiers": ["csv_semicolon"],
    },
}

# Intervalo entre sondeos al crawler si se desea esperar
CRAWLER_POLL = 30


def lambda_handler(event, context):
    glue = boto3.client("glue", region_name=REGION)

    _ensure_database(glue)

    crawlers_started = []

    for tbl, cfg in DATASETS.items():
        _ensure_crawler(glue, tbl, cfg)
        _start_crawler(glue, tbl, wait=False)
        crawlers_started.append(tbl)

    return {
        "status": "OK",
        "database": DB_NAME,
        "crawlers_started": crawlers_started,
    }


# ────────────── Funciones auxiliares ──────────────────────────────────────

def _ensure_database(glue):
    try:
        glue.get_database(Name=DB_NAME)
    except glue.exceptions.EntityNotFoundException:
        glue.create_database(
            DatabaseInput={
                "Name": DB_NAME,
                "Description": "Catálogo de datos SME Analytics",
            }
        )


def _ensure_crawler(glue, table_name, cfg):
    crawler_name = f"crawler_{table_name}"
    args = {
        "Name": crawler_name,
        "Role": GLUE_ROLE_ARN,
        "DatabaseName": DB_NAME,
        "Targets": {"S3Targets": [{"Path": cfg["path"]}]},
        "Classifiers": cfg.get("classifiers", []),
        "SchemaChangePolicy": {
            "UpdateBehavior": "UPDATE_IN_DATABASE",
            "DeleteBehavior": "LOG",
        },
    }

    try:
        glue.get_crawler(Name=crawler_name)
        glue.update_crawler(**args)
    except glue.exceptions.EntityNotFoundException:
        glue.create_crawler(**args)


def _start_crawler(glue, table_name, wait=False):
    crawler_name = f"crawler_{table_name}"

    state = glue.get_crawler(Name=crawler_name)["Crawler"]["State"]
    if state in {"READY", "STOPPING", "STOPPED"}:
        glue.start_crawler(Name=crawler_name)

    if not wait:
        return

    while True:
        crawl_info = glue.get_crawler(Name=crawler_name)["Crawler"]
        last_crawl = crawl_info.get("LastCrawl", {})
        status = last_crawl.get("Status")
        if status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            break
        time.sleep(CRAWLER_POLL)
