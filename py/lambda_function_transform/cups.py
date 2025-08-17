# cups.py
from __future__ import annotations

import io, os, unicodedata
from datetime import datetime, timezone, timedelta
from typing import List

import boto3
import pandas as pd

# ---------------------------- Constantes S3 -------------------------------
BUCKET = "serverless-architecture-smes-analytics-bronze-zone"
RAW_PREFIX        = "bronze1/procedimientos"
TRANSFORMED_PREFIX = "silver1/procedimientos/"
PROCESSED_PREFIX   = "bronze2/procedimientos/"
CO_TZ = timezone(timedelta(hours=-5))         # Colombia

# --------------------------- Utilidades -----------------------------------
def _remove_accents(text: str | None) -> str | None:
    if text is None:
        return None
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

def _normalize_column(name: str) -> str:
    return (
        _remove_accents(name)
        .lower()
        .replace("\n", " ")
        .replace("\r", " ")
        .strip()
    )

DESIRED_MAP: dict[str, str] = {
    "fecha": "fecha",
    "nombre del paciente": "nombre del paciente",
    "numero de documento - historia clinica": "numero de documento - historia clinica",
    "medico interno responsable": "medico interno responsable",
    "medico externo responsable": "medico externo responsable",
    "promotor de salud": "promotor de salud",
    "actividad/servicio": "actividad_servicio",
    "actividad / servicio": "actividad_servicio",
    "actividad servicio": "actividad_servicio",
}

KEY_COLS  = ["nombre del paciente", "numero de documento - historia clinica", "actividad_servicio"]
ORDERED_COLS = [
    "fecha",
    "nombre del paciente",
    "numero de documento - historia clinica",
    "medico interno responsable",
    "medico externo responsable",
    "promotor de salud",
    "actividad_servicio",
]

# ------------------------- API reutilizable -------------------------------
def process_cups(event=None, context=None) -> dict:
    """Procesa los archivos .xlsx de procedimientos (CUPS) y devuelve metadatos."""
    s3 = boto3.client("s3")

    paginator   = s3.get_paginator("list_objects_v2")
    excel_keys: List[str] = [
        obj["Key"]
        for page in paginator.paginate(Bucket=BUCKET, Prefix=RAW_PREFIX)
        for obj in page.get("Contents", [])
        if obj["Key"].lower().endswith(".xlsx")
    ]

    if not excel_keys:
        return {"status": "NO_DATA", "message": "No se encontraron archivos .xlsx"}

    frames: List[pd.DataFrame] = []
    for key in excel_keys:
        body = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
        df   = pd.read_excel(io.BytesIO(body), dtype=str, engine="openpyxl")

        rename_map = {
            col: DESIRED_MAP[_normalize_column(col)]
            for col in df.columns
            if _normalize_column(col) in DESIRED_MAP
        }
        df = df[list(rename_map)].rename(columns=rename_map)

        for canonical in DESIRED_MAP.values():
            if canonical not in df.columns:
                df[canonical] = ""

        df = df.applymap(lambda x: str(x).strip() if pd.notna(x) else "")

        df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce")
        df["fecha"] = df["fecha"].apply(
            lambda d: d.replace(year=2024) if pd.notnull(d) and d.year == 2023 else d
        )

        frames.append(df)

    consol = pd.concat(frames, ignore_index=True)
    consol.replace({"": pd.NA}, inplace=True)
    consol.dropna(how="all", subset=KEY_COLS, inplace=True)
    consol.fillna("", inplace=True)

    consol["fecha"] = pd.to_datetime(consol["fecha"], errors="coerce").dt.strftime("%d/%m/%Y")
    consol = consol[ORDERED_COLS]

    timestamp      = datetime.now(CO_TZ).strftime("%d%m%Y%H%M")
    final_filename = f"consolidado_procedimientos_{timestamp}.csv"
    csv_buffer     = io.BytesIO()
    consol.to_csv(csv_buffer, index=False, encoding="utf-8-sig", lineterminator="\n")
    csv_buffer.seek(0)

    final_key = f"{TRANSFORMED_PREFIX}{final_filename}"
    s3.put_object(Bucket="serverless-architecture-smes-analytics-silver-zone", Key=final_key, Body=csv_buffer.getvalue())

    for key in excel_keys:
        dest_key = f"{PROCESSED_PREFIX}{os.path.basename(key)}"
        s3.copy_object(Bucket=BUCKET, CopySource={"Bucket": BUCKET, "Key": key}, Key=dest_key)
        s3.delete_object(Bucket=BUCKET, Key=key)

    return {
        "status": "SUCCESS",
        "rows": len(consol),
        "output": f"s3://{BUCKET}/{final_key}",
        "moved": len(excel_keys),
    }

# --- wrapper opcional para ejecutar cups.py de forma aislada --------------
def lambda_handler(event, context):  # pragma: no cover
    return process_cups(event, context)
