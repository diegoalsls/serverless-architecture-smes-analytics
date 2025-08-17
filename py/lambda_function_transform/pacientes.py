# pacientes.py
from __future__ import annotations

import io, unicodedata, csv
from datetime import datetime, timezone, timedelta

import boto3
import pandas as pd

# ------------------  Constantes S3 y zona horaria -------------------------
BUCKET                 = "serverless-architecture-smes-analytics-bronze-zone"
PATIENTS_RAW_KEY       = "bronze1/pacientes/pacientes.csv"
PATIENTS_PROCESSED_KEY = "bronze2/pacientes/pacientes.csv"
PATIENTS_OUTPUT_KEY    = "gold1/pacientes/pacientes.csv"
CO_TZ = timezone(timedelta(hours=-5))   # Colombia

# -------------------- Helpers --------------------------------------------
def _normalize(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(c)).lower().strip()

def _read_patients_csv(raw: bytes) -> pd.DataFrame:
    for enc in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            return pd.read_csv(
                io.BytesIO(raw), dtype=str, encoding=enc,
                sep=";", engine="python", on_bad_lines="skip"
            )
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    return pd.read_csv(
        io.BytesIO(raw), dtype=str, encoding="utf-8",
        sep=";", engine="python", on_bad_lines="skip", encoding_errors="replace"
    )

# ------------------ API reutilizable -------------------------------------
def process_pacientes(event=None, context=None) -> dict:
    s3 = boto3.client("s3")

    try:
        obj = s3.get_object(Bucket=BUCKET, Key=PATIENTS_RAW_KEY)
    except s3.exceptions.NoSuchKey:
        return {"status": "NO_DATA", "message": f"{PATIENTS_RAW_KEY} no existe"}

    df = _read_patients_csv(obj["Body"].read())
    df.columns = df.columns.str.strip()

    # ---- nombre_completo -------------------------------------------------
    col_map = {_normalize(c): c for c in df.columns}
    canonical = ["primer nombre", "segundo nombre", "primer apellido", "segundo apellido"]
    parts, drop_cols = [], []
    for key in canonical:
        real = col_map.get(key)
        parts.append(df[real].fillna("") if real else "")
        if real:
            drop_cols.append(real)

    df["nombre_completo"] = (
        (parts[0] + " " + parts[1] + " " + parts[2] + " " + parts[3])
        .str.replace(r"\s+", " ", regex=True).str.strip()
    )
    if drop_cols:
        df.drop(columns=drop_cols, inplace=True)

    # ---- Sexo / género ----------------------------------------------------
    genero_col = next((c for c in df.columns if _normalize(c) == "identidad de genero"), None)
    if genero_col and genero_col != "genero":
        df.rename(columns={genero_col: "genero"}, inplace=True)
    if "genero" not in df.columns:
        df["genero"] = ""

    df["Sexo"]   = df.get("Sexo", "").fillna("").str.upper().str.strip()
    df["genero"] = df["genero"].fillna("").str.title().str.strip()

    mask = (df["genero"] == "") & df["Sexo"].isin(["F", "M"])
    df.loc[mask, "genero"] = df.loc[mask, "Sexo"].map({"F": "Femenino", "M": "Masculino"})
    mask = df["Sexo"].isin(["", "0"]) & df["genero"].isin(["Femenino", "Masculino"])
    df.loc[mask, "Sexo"] = df.loc[mask, "genero"].map({"Femenino": "F", "Masculino": "M"})

    # ---- Fecha ingreso ----------------------------------------------------
    if "Fecha Ingreso" in df.columns:
        df["Fecha Ingreso"] = pd.to_datetime(df["Fecha Ingreso"], errors="coerce").dt.strftime("%d/%m/%Y")

    # ---- Guardar en gold --------------------------------------------------
    out = io.BytesIO()
    df.to_csv(out, index=False, encoding="utf-8-sig", sep=";", lineterminator="\n")
    out.seek(0)
    s3.put_object(Bucket="serverless-architecture-smes-analytics-gold-zone", Key=PATIENTS_OUTPUT_KEY, Body=out.getvalue())

    s3.copy_object(
        Bucket=BUCKET, CopySource={"Bucket": BUCKET, "Key": PATIENTS_RAW_KEY},
        Key=PATIENTS_PROCESSED_KEY
    )
    s3.delete_object(Bucket=BUCKET, Key=PATIENTS_RAW_KEY)

    return {
        "status": "SUCCESS",
        "rows": len(df),
        "output": f"s3://serverless-architecture-smes-analytics-gold-zone/{PATIENTS_OUTPUT_KEY}",
        "moved_from": PATIENTS_RAW_KEY,
        "moved_to": PATIENTS_PROCESSED_KEY,
        "timestamp": datetime.now(CO_TZ).isoformat(),
    }

# ----- wrapper opcional para ejecutar pacientes.py de forma aislada -------
def lambda_handler(event, context):  # pragma: no cover
    return process_pacientes(event, context)
