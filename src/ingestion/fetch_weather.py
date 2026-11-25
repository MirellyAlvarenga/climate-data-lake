import json
import logging
import random
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


def fetch_city_weather(
    city_info: dict,
    start_date: str,
    end_date: str,
    max_retries: int = 3,
    base_backoff: int = 15,
) -> dict:
    """Consulta a série histórica na Open-Meteo com backoff exponencial e jitter."""
    params = {
        "latitude": city_info["latitude"],
        "longitude": city_info["longitude"],
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": "America/Sao_Paulo",
    }

    for attempt in range(1, max_retries + 1):
        response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=30)

        if response.status_code == 429:
            # Exponencial (15s, 30s, 60s) + jitter aleatório de até 2s
            wait_seconds = base_backoff * (2 ** (attempt - 1)) + random.uniform(0, 2)
            logger.warning(
                "Rate limit (429) atingido para %s. Aguardando %.1fs (tentativa %d/%d)...",
                city_info["name"],
                wait_seconds,
                attempt,
                max_retries,
            )
            time.sleep(wait_seconds)
            continue

        response.raise_for_status()
        return response.json()

    raise requests.HTTPError(
        f"Limite de tentativas excedido (HTTP 429) para {city_info['name']}."
    )


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


def run_ingestion(force: bool = False) -> None:
    """Executa o pipeline de extração para todas as cidades configuradas."""
    logger.info(
        "Iniciando ingestão Bronze (%s até %s) para %d cidades...",
        START_DATE,
        END_DATE,
        len(CITIES),
    )

    for city_slug, city_info in CITIES.items():
        output_path = BRONZE_DIR / f"{city_slug}_raw.json"

        if output_path.exists() and not force:
            logger.info("Já existente na Bronze: %s (pulando extração)", output_path.name)
            continue

        try:
            logger.info("Extraindo dados de %s (%s)...", city_info["name"], city_info["state"])
            payload = fetch_city_weather(city_info, START_DATE, END_DATE)
            saved_path = save_to_bronze(city_slug, city_info, payload)

            total_days = len(payload.get("daily", {}).get("time", []))
            logger.info("Salvo com sucesso: %s (%d registros diários)", saved_path.name, total_days)

            time.sleep(5)

        except requests.RequestException as exc:
            logger.error("Falha na requisição para %s: %s", city_info["name"], exc)

    logger.info("Ingestão da camada Bronze concluída.")


if __name__ == "__main__":
    run_ingestion()