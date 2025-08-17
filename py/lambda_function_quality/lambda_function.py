from __future__ import annotations

import io
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import List

import boto3
import pandas as pd

# ----------------------- S3 y zona horaria ---------------------------------
BUCKET = "serverless-architecture-smes-analytics-silver-zone"
SILVER1_PREFIX = "silver1/procedimientos/"
SILVER2_PREFIX = "silver2/procedimientos/"
GOLD1_PREFIX = "gold1/procedimientos/"
PACIENTES_KEY = "gold1/pacientes/pacientes.csv"
CO_TZ = timezone(timedelta(hours=-5))  # America/Bogota

# ----------------------- Cliente AWS --------------------------------------
s3 = boto3.client("s3")
glue = boto3.client("glue")            # <-- para lanzar el job

# --------------------- Utilidades generales --------------------------------
def _remove_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

RM_PATTERN = re.compile(r"\bRM[:\s]*([0-9][0-9\.\,]*)", re.IGNORECASE)

def _split_responsable(val: str | float | int) -> tuple[str, str]:
    if not isinstance(val, str):
        return "sin responsable", "sin RM"

    original = val.strip()
    if original == "":
        return "sin responsable", "sin RM"

    match = RM_PATTERN.search(original)
    rm_clean = re.sub(r"[^0-9]", "", match.group(1)) if match else "sin RM"

    nombre = RM_PATTERN.sub("", original).rstrip(" -").strip()
    if nombre == "":
        nombre = "sin responsable"

    return nombre, rm_clean

# ---------- clasificación tipo de procedimiento ---------------------------
PROC_MAP = {
    "biopuntura": "biopuntura",
    "ozonoterapia": "ozonoterapia",
    "sueroterapia": "sueroterapia",
    "terapia neural": "terapia neural",
}

def _clasificar_proc(actividad: str | float | int) -> str:
    if not isinstance(actividad, str):
        return "otro"
    act_low = _remove_accents(actividad.lower())
    for clave, categoria in PROC_MAP.items():
        if clave in act_low:
            return categoria
    return "otro"

# ---------------------- Lambda handler ------------------------------------
def lambda_handler(event, context):  # noqa: N802
    # 0) ¿Debemos lanzar el Glue Job?
    job_run_id = None
    try:
        head = s3.head_object(Bucket="serverless-architecture-smes-analytics-gold-zone", Key=PACIENTES_KEY)
        last_mod: datetime = head["LastModified"]         # UTC tz-aware
        age_sec = (datetime.now(timezone.utc) - last_mod).total_seconds()

        if age_sec <= 600:  # 10 minutos
            resp = glue.start_job_run(JobName="prediction_pacientes")
            job_run_id = resp["JobRunId"]
    except s3.exceptions.NoSuchKey:
        # El archivo pacientes.csv aún no existe; simplemente continúa
        pass

    # 1) Listar CSV en silver1
    paginator = s3.get_paginator("list_objects_v2")
    csv_keys: List[str] = [
        obj["Key"]
        for page in paginator.paginate(Bucket=BUCKET, Prefix=SILVER1_PREFIX)
        for obj in page.get("Contents", [])
        if obj["Key"].lower().endswith(".csv")
    ]

    if not csv_keys:
        return {
            "status": "NO_DATA",
            "message": "No se encontraron CSV en silver1",
            "triggered_job": job_run_id,
        }

    frames: List[pd.DataFrame] = []

    # 2) Leer y transformar
    for key in csv_keys:
        body = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
        df = pd.read_csv(io.BytesIO(body), dtype=str, encoding="utf-8-sig")

        # 2.1 split responsable & RM
        nombres, rms = zip(*df["medico interno responsable"].map(_split_responsable))
        df["medico interno responsable"] = nombres
        df["rm"] = rms

        # 2.2 tipo de procedimiento
        df["tipo de procedimiento"] = df["actividad_servicio"].map(_clasificar_proc)

        frames.append(df)

    # 3) Consolidar
    gold = pd.concat(frames, ignore_index=True)

    # 4) Guardar a gold1 con timestamp Bogotá
    ts = datetime.now(CO_TZ).strftime("%d%m%Y%H%M")
    gold_name = f"procedimientos_gold_{ts}.csv"
    csv_buffer = io.BytesIO()
    gold.to_csv(csv_buffer, index=False, encoding="utf-8-sig", lineterminator="\n")
    csv_buffer.seek(0)
    gold_key = f"{GOLD1_PREFIX}{gold_name}"
    s3.put_object(Bucket="serverless-architecture-smes-analytics-gold-zone", Key=gold_key, Body=csv_buffer.getvalue())

    # 5) Mover CSV procesados a silver2
    for key in csv_keys:
        dest_key = f"{SILVER2_PREFIX}{os.path.basename(key)}"
        s3.copy_object(
            Bucket=BUCKET, CopySource={"Bucket": BUCKET, "Key": key}, Key=dest_key
        )
        s3.delete_object(Bucket=BUCKET, Key=key)

    return {
        "status": "SUCCESS",
        "processed_files": len(csv_keys),
        "output": f"s3://{BUCKET}/{gold_key}",
        "triggered_job": job_run_id,
    }
