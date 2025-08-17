# mensual_proc.py
from __future__ import annotations
import io, unicodedata, re
from datetime import datetime, timezone, timedelta
from typing import List

import boto3
import pandas as pd

# ─────────── Constantes S3 y zona horaria ────────────────────────────────
BUCKET        = "serverless-architecture-smes-analytics-bronze-zone"
RAW_XLSX_KEY  = "bronze1/mensual_proc/mensual_procedimientos.xlsx"
PROC_XLSX_KEY = "bronze2/mensual_proc/mensual_procedimientos.xlsx"

CO_TZ         = timezone(timedelta(hours=-5))  # Colombia (UTC-5)
timestamp      = datetime.now(CO_TZ).strftime("%d%m%Y%H%M")
GOLD_CSV_KEY  = f"gold1/mensual_proc/consolidado_procedimientos_{timestamp}.csv"


# ─────────── Utilidades ──────────────────────────────────────────────────
def _noacc(s: str) -> str:
    """Devuelve s sin tildes y en minúsculas, listo para comparar."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    ).lower().strip()

SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

TARGET_COLS = [
    "procedimiento", "numero de eventos", "efectos adversos", "utilidad promedio",
    "ingresos promedio por procedimiento",
    "equipo de promoción procedimientos menores", "equipode promoción laboratorio",
    "equipo de promoción medicina estética", "equipo de promoción exámenes diagnosticos complementarios",
    "equipo de crecimiento y calidad procedimientos menores", "equipo de crecimiento y calidad laboratorio",
    "equipo de crecimiento y calidad medicina estética", "equipo de crecimiento y calidad exámenes diagnosticos complementarios",
]

NORM_COLS  = [_noacc(c) for c in TARGET_COLS]       # nombres normalizados
EQUIP_COLS = [c for c in NORM_COLS if "equipo" in c]  # columnas de equipo
MONTH_RE   = re.compile(
    r"^(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+2024$",
    re.I,
)

# ─────────── Proceso principal reutilizable ──────────────────────────────
def process_mensual_proc(event=None, context=None) -> dict:
    """
    Consolida las 12 pestañas mensuales del archivo Excel en un único CSV,
    limpia tildes, normaliza encabezados y agrega la columna 'fecha'.
    """
    s3 = boto3.client("s3")

    # 1. Descargar el Excel de origen
    try:
        raw = s3.get_object(Bucket=BUCKET, Key=RAW_XLSX_KEY)["Body"].read()
    except s3.exceptions.NoSuchKey:
        return {"status": "NO_DATA", "message": f"{RAW_XLSX_KEY} no existe"}

    wb = pd.ExcelFile(io.BytesIO(raw))
    frames: List[pd.DataFrame] = []

    # 2. Procesar cada pestaña “MES 2024”
    for sheet in wb.sheet_names:
        m = MONTH_RE.match(sheet)
        if not m:
            continue

        month_name = m.group(1).lower()
        month_num  = SPANISH_MONTHS[month_name]
        fecha_const = f"01/{month_num:02d}/2024"   # dd/mm/aaaa

        df = wb.parse(sheet_name=sheet, dtype=str)
        df.columns = [_noacc(c) for c in df.columns]

        # Cortar desde “numero total de eventos” hacia abajo
        cutoff = df[df.iloc[:, 0].str.contains("numero total de eventos", case=False, na=False)].index
        if not cutoff.empty:
            df = df.loc[: cutoff[0] - 1]

        # Quedarnos con las columnas objetivo y crear faltantes
        df = df[[c for c in df.columns if c in NORM_COLS]]
        for col in NORM_COLS:
            if col not in df.columns:
                df[col] = ""

        # Extender valores únicos en columnas de equipo
        for col in EQUIP_COLS:
            uniq = df[col].dropna().unique()
            if len(uniq) == 1:
                df[col] = uniq[0]
            else:
                df[col].fillna(method="ffill", inplace=True)

        df["fecha"] = fecha_const
        frames.append(df[NORM_COLS + ["fecha"]])

    if not frames:
        return {"status": "NO_DATA", "message": "No se encontraron pestañas válidas"}

    # 3. Unir y escribir resultado a Gold
    final = pd.concat(frames, ignore_index=True)
    buf = io.BytesIO()
    final.to_csv(buf, index=False, sep=";", encoding="utf-8-sig", lineterminator="\n")
    buf.seek(0)

    s3.put_object(Bucket="serverless-architecture-smes-analytics-gold-zone", Key=GOLD_CSV_KEY, Body=buf.getvalue())
    # Mover el archivo original a bronze2
    s3.copy_object(Bucket=BUCKET, CopySource={"Bucket": BUCKET, "Key": RAW_XLSX_KEY}, Key=PROC_XLSX_KEY)
    s3.delete_object(Bucket=BUCKET, Key=RAW_XLSX_KEY)

    return {
        "status": "SUCCESS",
        "rows": len(final),
        "output": f"s3://serverless-architecture-smes-analytics-gold-zone/{GOLD_CSV_KEY}",
        "moved_from": RAW_XLSX_KEY,
        "moved_to": PROC_XLSX_KEY,
        "timestamp": datetime.now(CO_TZ).isoformat(),
    }

# ─────────── Wrapper — permite usar esta Lambda de forma independiente ───
def lambda_handler(event, context):  # pragma: no cover
    return process_mensual_proc(event, context)
