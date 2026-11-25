import json
import logging
import shutil
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.utils.config import BRONZE_DIR, SILVER_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

NUMERIC_COLUMNS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "rain_sum",
    "wind_speed_10m_max",
    "shortwave_radiation_sum",
]


def get_southern_hemisphere_season(month: int) -> str:
    """Mapeia o número do mês para a estação climática do Hemisfério Sul."""
    if month in (12, 1, 2):
        return "Verão"
    if month in (3, 4, 5):
        return "Outono"
    if month in (6, 7, 8):
        return "Inverno"
    return "Primavera"


def parse_bronze_file(file_path: Path) -> pd.DataFrame:
    """Lê um JSON bruto da Bronze e achata a série diária com seus metadados."""
    with file_path.open("r", encoding="utf-8") as file:
        document = json.load(file)

    metadata = document.get("metadata", {})
    daily_data = document.get("data", {}).get("daily", {})

    df = pd.DataFrame(daily_data)
    df["city_slug"] = metadata.get("city_slug")
    df["city_name"] = metadata.get("city_name")
    df["state"] = metadata.get("state")
    df["region"] = metadata.get("region")
    df["ingested_at_utc"] = metadata.get("ingested_at_utc")

    return df


def transform_to_silver(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica tipagem estrita, deduplicação e enriquecimento climático."""
    df = df.rename(columns={"time": "date"}).copy()

    # Conversão de data e ordenação cronológica
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "city_slug"])
    df = df.sort_values(["city_slug", "date"]).drop_duplicates(
        subset=["city_slug", "date"], keep="last"
    )

    # Tipagem numérica explícita
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    # Tratamento de nulos residuais em precipitação/radiação (preenche com 0.0 quando ausente)
    for col in ("precipitation_sum", "rain_sum"):
        df[col] = df[col].fillna(0.0)

    # Colunas temporais e de particionamento
    df["year"] = df["date"].dt.year.astype("int32")
    df["month"] = df["date"].dt.month.astype("int32")
    df["season"] = df["month"].map(get_southern_hemisphere_season)

    # Métricas derivadas de negócio/clima
    df["temp_amplitude"] = (df["temperature_2m_max"] - df["temperature_2m_min"]).round(2)
    # Limiar meteorológico padrão para considerar um dia chuvoso (>= 1.0 mm)
    df["is_rainy_day"] = df["precipitation_sum"] >= 1.0

    # Converte timestamp para date puro (date32 no Parquet)
    df["date"] = df["date"].dt.date

    ordered_columns = [
        "date",
        "year",
        "month",
        "season",
        "city_slug",
        "city_name",
        "state",
        "region",
        "temperature_2m_max",
        "temperature_2m_min",
        "temperature_2m_mean",
        "temp_amplitude",
        "precipitation_sum",
        "rain_sum",
        "is_rainy_day",
        "wind_speed_10m_max",
        "shortwave_radiation_sum",
        "ingested_at_utc",
    ]
    return df[ordered_columns].reset_index(drop=True)


def save_partitioned_parquet(df: pd.DataFrame, output_dir: Path) -> int:
    """Grava o DataFrame em Parquet particionado por cidade e ano (idempotente)."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_to_dataset(
        table,
        root_path=str(output_dir),
        partition_cols=["city_slug", "year"],
        compression="snappy",
    )

    parquet_files = list(output_dir.rglob("*.parquet"))
    return len(parquet_files)


def run_bronze_to_silver() -> None:
    """Orquestra a leitura da camada Bronze e escrita na camada Silver."""
    bronze_files = sorted(BRONZE_DIR.glob("*_raw.json"))
    if not bronze_files:
        raise FileNotFoundError(
            f"Nenhum arquivo bruto encontrado em {BRONZE_DIR}. Execute fetch_weather primeiro."
        )

    logger.info("Lendo %d arquivos da camada Bronze...", len(bronze_files))
    raw_frames = [parse_bronze_file(path) for path in bronze_files]
    combined_df = pd.concat(raw_frames, ignore_index=True)

    logger.info("Transformando e validando %d registros...", len(combined_df))
    silver_df = transform_to_silver(combined_df)

    null_summary = silver_df[NUMERIC_COLUMNS].isna().sum().to_dict()
    logger.info("Resumo de nulos pós-limpeza: %s", null_summary)

    silver_dataset_dir = SILVER_DIR / "weather_daily"
    total_files = save_partitioned_parquet(silver_df, silver_dataset_dir)

    logger.info(
        "Camada Silver concluída: %d registros salvos em %d partições Parquet (%s).",
        len(silver_df),
        total_files,
        silver_dataset_dir,
    )


if __name__ == "__main__":
    run_bronze_to_silver()