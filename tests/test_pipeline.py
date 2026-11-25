import duckdb
import pandas as pd
import pytest

from src.processing.bronze_to_silver import (
    get_southern_hemisphere_season,
    transform_to_silver,
)
from src.utils.config import CITIES, GOLD_DIR


def test_southern_hemisphere_seasons() -> None:
    """Valida o mapeamento correto das estações do ano no Hemisfério Sul."""
    assert get_southern_hemisphere_season(1) == "Verão"
    assert get_southern_hemisphere_season(4) == "Outono"
    assert get_southern_hemisphere_season(7) == "Inverno"
    assert get_southern_hemisphere_season(10) == "Primavera"


def test_transform_to_silver_deduplication_and_metrics() -> None:
    """Garante deduplicação por cidade/data e cálculo correto de amplitude e chuva."""
    mock_raw = pd.DataFrame(
        [
            {
                "time": "2025-01-15",
                "city_slug": "belo_horizonte",
                "city_name": "Belo Horizonte",
                "state": "MG",
                "region": "Sudeste",
                "temperature_2m_max": 30.0,
                "temperature_2m_min": 18.5,
                "temperature_2m_mean": 24.0,
                "precipitation_sum": 0.0,
                "rain_sum": 0.0,
                "wind_speed_10m_max": 15.2,
                "shortwave_radiation_sum": 22.1,
                "ingested_at_utc": "2026-01-01T00:00:00Z",
            },
            # Registro duplicado na mesma data com valor atualizado (deve prevalecer)
            {
                "time": "2025-01-15",
                "city_slug": "belo_horizonte",
                "city_name": "Belo Horizonte",
                "state": "MG",
                "region": "Sudeste",
                "temperature_2m_max": 31.5,
                "temperature_2m_min": 19.0,
                "temperature_2m_mean": 25.0,
                "precipitation_sum": 12.4,
                "rain_sum": 12.4,
                "wind_speed_10m_max": 18.0,
                "shortwave_radiation_sum": 20.5,
                "ingested_at_utc": "2026-01-02T00:00:00Z",
            },
        ]
    )

    result = transform_to_silver(mock_raw)

    assert len(result) == 1
    row = result.iloc[0]
    assert row["temperature_2m_max"] == 31.5
    assert row["temp_amplitude"] == 12.5
    assert bool(row["is_rainy_day"]) is True
    assert row["season"] == "Verão"


@pytest.mark.skipif(
    not (GOLD_DIR / "gold_city_kpis.parquet").exists(),
    reason="Arquivos Gold ainda não materializados no ambiente.",
)
def test_gold_layer_data_quality() -> None:
    """Valida integridade referencial, unicidade e limites físicos na camada Gold."""
    daily_path = (GOLD_DIR / "gold_daily_timeseries.parquet").as_posix()
    monthly_path = (GOLD_DIR / "gold_monthly_summary.parquet").as_posix()
    kpis_path = (GOLD_DIR / "gold_city_kpis.parquet").as_posix()

    with duckdb.connect(database=":memory:") as con:
        # 1. Todas as 5 capitais configuradas devem estar presentes nos KPIs
        city_count = con.execute(
            f"SELECT COUNT(DISTINCT city_slug) FROM read_parquet('{kpis_path}')"
        ).fetchone()[0]
        assert city_count == len(CITIES)

        # 2. Chave primária lógica (city_slug, date) sem duplicatas na série diária
        dup_count = con.execute(f"""
            SELECT COUNT(*) FROM (
                SELECT city_slug, date, COUNT(*) AS cnt
                FROM read_parquet('{daily_path}')
                GROUP BY city_slug, date
                HAVING cnt > 1
            )
        """).fetchone()[0]
        assert dup_count == 0

        # 3. Consistência física: temp máxima >= mínima e precipitação não negativa
        invalid_physics = con.execute(f"""
            SELECT COUNT(*)
            FROM read_parquet('{daily_path}')
            WHERE temperature_2m_max < temperature_2m_min
               OR precipitation_sum < 0
               OR temp_ma_30d IS NULL
        """).fetchone()[0]
        assert invalid_physics == 0

        # 4. Série mensal deve conter exatamente 12 meses distintos por cidade
        months_per_city = con.execute(f"""
            SELECT MIN(month_cnt) FROM (
                SELECT city_slug, COUNT(DISTINCT month) AS month_cnt
                FROM read_parquet('{monthly_path}')
                GROUP BY city_slug
            )
        """).fetchone()[0]
        assert months_per_city == 12