import io, json, re, unicodedata, logging, boto3
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

# ─────────────────────────────── Configuración ───────────────────────────────
logger = logging.getLogger("glue-logreg")
logger.setLevel(logging.INFO)

REGION        = "us-east-1"
DB_NAME       = "smes_analytics"
GLUE_ROLE_ARN = "arn:aws:iam::#cuenta:role/glue_service_role_for_crawlers"
LAMBDA_NAME   = "LambdaGlue"

BUCKET             = "serverless-architecture-smes-analytics-gold-zone"
PATIENTS_KEY       = "gold1/pacientes/pacientes.csv"
PROCS_PREFIX       = "gold1/procedimientos/"
OUTPUT_BUCKET      = "serverless-architecture-smes-analytics-predictive"
OUTPUT_KEY         = "prediction/recomendacion_procedimientos/recomendacion.csv"
RECOMENDACION_PATH = f"s3://{OUTPUT_BUCKET}/prediction/recomendacion_procedimientos/"

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
        "path": RECOMENDACION_PATH,
        "classifiers": ["csv_comma"],
    },
    "consolidado_procedimientos": {
        "path": "s3://serverless-architecture-smes-analytics-gold-zone/gold1/mensual_proc/",
        "classifiers": ["csv_semicolon"],
    },
}

s3 = boto3.client("s3")
glue = boto3.client("glue", region_name=REGION)
lambda_client = boto3.client("lambda", region_name=REGION)

# ───────────────────── Utilidades ------------------------------------------------
def normalize_name(name: str) -> str:
    if pd.isna(name): return ""
    n = unicodedata.normalize("NFD", str(name).strip().upper())
    return "".join(c for c in n if unicodedata.category(c) != "Mn")

def age_to_years(raw):
    if pd.isna(raw): return np.nan
    m = re.search(r"(\d+)", str(raw))
    return float(m.group(1)) if m else np.nan

def read_csv_from_s3(key: str, delimiter: str = ",") -> pd.DataFrame:
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    return pd.read_csv(io.BytesIO(obj["Body"].read()), encoding="utf-8-sig", delimiter=delimiter)

def load_patients_and_procs():
    df_pat = read_csv_from_s3(PATIENTS_KEY, delimiter=";")
    df_pat["name_norm"] = df_pat["nombre_completo"].apply(normalize_name)
    df_pat["age_years"] = df_pat["Edad actual"].apply(age_to_years)

    paginator = s3.get_paginator("list_objects_v2")
    frames = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PROCS_PREFIX):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".csv"):
                frames.append(read_csv_from_s3(obj["Key"]))
    df_proc = pd.concat(frames, ignore_index=True)
    df_proc["name_norm"] = df_proc["nombre del paciente"].apply(normalize_name)
    return df_pat, df_proc

# ───────────────────── Modelado ------------------------------------------------
def build_and_train(df_join):
    feature_cols = ["genero", "age_years"]
    X, y = df_join[feature_cols], df_join["tipo de procedimiento"]

    X_tr, X_ts, y_tr, y_ts = train_test_split(X, y, test_size=0.20, stratify=y, random_state=42)

    preprocess = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), ["genero"]),
        ("num", "passthrough", ["age_years"]),
    ])

    pipe = Pipeline([
        ("prep", preprocess),
        ("model", LogisticRegression(max_iter=1_000, multi_class="multinomial")),
    ])
    pipe.fit(X_tr, y_tr)

    y_pred = pipe.predict(X_ts)
    logger.info("Exactitud (test) = %.4f", accuracy_score(y_ts, y_pred))
    logger.info("\n%s", classification_report(y_ts, y_pred, zero_division=0))
    return pipe

# ───────────────────── Predicción y carga a S3 ---------------------------------
def predict_and_upload(pipe, df_pat):
    feature_cols = ["genero", "age_years"]
    pred_df = df_pat[["Id Paciente", "nombre_completo", "genero", "age_years"]].copy()
    mask = pred_df["genero"].notna() & pred_df["age_years"].notna()
    pred_df.loc[mask, "predicted_tipo_procedimiento"] = pipe.predict(
        pred_df.loc[mask, feature_cols]
    )
    pred_df["predicted_tipo_procedimiento"].fillna("unknown", inplace=True)

    buf = io.StringIO()
    pred_df.to_csv(buf, index=False)
    buf.seek(0)

    s3.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=OUTPUT_KEY,
        Body=buf.getvalue().encode("utf-8-sig"),
        ContentType="text/csv",
    )
    logger.info("Archivo escrito → s3://%s/%s", OUTPUT_BUCKET, OUTPUT_KEY)

# ───────────────────── Validación Glue posterior a predicción ------------------
def validate_glue_components():
    try:
        glue.get_database(Name=DB_NAME)
    except glue.exceptions.EntityNotFoundException:
        logger.warning("Base de datos no existe.")
        return False

    for tbl in DATASETS:
        name = f"crawler_{tbl}"
        try:
            glue.get_crawler(Name=name)
        except glue.exceptions.EntityNotFoundException:
            logger.warning("Crawler no existe: %s", name)
            return False

    return True

def invoke_lambda_to_create_components():
    logger.warning("Faltan componentes en Glue. Ejecutando LambdaGlue…")
    response = lambda_client.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({}),
    )
    payload = json.load(response["Payload"])
    logger.info("Respuesta LambdaGlue: %s", json.dumps(payload, indent=2))

# ───────────────────── Pipeline completo ---------------------------------------
def run_pipeline():
    logger.info("▶ Ejecutando pipeline predictivo…")
    df_pat, df_proc = load_patients_and_procs()

    df_join = (df_pat
               .merge(df_proc[["name_norm", "tipo de procedimiento"]],
                      on="name_norm", how="inner")
               .dropna(subset=["genero", "age_years", "tipo de procedimiento"])
               .drop_duplicates(subset=["name_norm"]))

    logger.info("Pacientes con historial = %d", df_join["name_norm"].nunique())
    model = build_and_train(df_join)
    predict_and_upload(model, df_pat)

    # Validación y llamada a Lambda si falta algo
    if not validate_glue_components():
        invoke_lambda_to_create_components()
    else:
        logger.info("✔ Todos los componentes de Glue existen.")

    logger.info("Pipeline finalizado ✅")

# ───────────────────── Ejecutar ------------------------------------------------
run_pipeline()

