import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.utils.config import (
    BRONZE_DIR,
    CITIES,
    DAILY_VARIABLES,
    END_DATE,
    OPEN_METEO_ARCHIVE_URL,
    START_DATE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def fetch_city_weather(city_info: dict, start_date: str, end_date: str) -> dict:
    """Consulta a série histórica diária na Open-Meteo API para uma coordenada."""
    params = {
        "latitude": city_info["latitude"],
        "longitude": city_info["longitude"],
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": "America/Sao_Paulo",
    }

    response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def save_to_bronze(city_slug: str, city_info: dict, raw_payload: dict) -> Path:
    """Persiste o JSON bruto na camada Bronze envelopado com metadados de ingestão."""
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BRONZE_DIR / f"{city_slug}_raw.json"

    bronze_document = {
        "metadata": {
            "city_slug": city_slug,
            "city_name": city_info["name"],
            "state": city_info["state"],
            "region": city_info["region"],
            "ingested_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "open-meteo-archive-api",
        },
        "data": raw_payload,
    }

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(bronze_document, file, ensure_ascii=False, indent=2)

    return output_path


def run_ingestion() -> None:
    """Executa o pipeline de extração para todas as cidades configuradas."""
    logger.info(
        "Iniciando ingestão Bronze (%s até %s) para %d cidades...",
        START_DATE,
        END_DATE,
        len(CITIES),
    )

    for city_slug, city_info in CITIES.items():
        try:
            logger.info("Extraindo dados de %s (%s)...", city_info["name"], city_info["state"])
            payload = fetch_city_weather(city_info, START_DATE, END_DATE)
            saved_path = save_to_bronze(city_slug, city_info, payload)

            total_days = len(payload.get("daily", {}).get("time", []))
            logger.info("Salvo com sucesso: %s (%d registros diários)", saved_path.name, total_days)

            # Pausa curta para evitar rate limit (HTTP 429) da API pública
            time.sleep(1)

        except requests.RequestException as exc:
            logger.error("Falha na requisição para %s: %s", city_info["name"], exc)

    logger.info("Ingestão da camada Bronze concluída.")


if __name__ == "__main__":
    run_ingestion()