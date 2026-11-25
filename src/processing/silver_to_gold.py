import logging
from pathlib import Path

import duckdb

from src.utils.config import GOLD_DIR, SILVER_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def build_gold_tables(con: duckdb.DuckDBPyConnection, silver_glob: str) -> dict[str, Path]:
    """Executa queries analíticas no DuckDB e exporta as tabelas Gold em Parquet."""
    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    outputs = {
        "daily_timeseries": GOLD_DIR / "gold_daily_timeseries.parquet",
        "monthly_summary": GOLD_DIR / "gold_monthly_summary.parquet",
        "city_kpis": GOLD_DIR / "gold_city_kpis.parquet",
    }

    # View virtual sobre o Data Lake particionado (ativa partition pruning e predicate pushdown)
    con.execute(f"""
        CREATE OR REPLACE VIEW silver_weather AS
        SELECT
            date,
            CAST(year AS INTEGER) AS year,
            month,
            season,
            city_slug,
            city_name,
            state,
            region,
            temperature_2m_max,
            temperature_2m_min,
            temperature_2m_mean,
            temp_amplitude,
            precipitation_sum,
            rain_sum,
            is_rainy_day,
            wind_speed_10m_max,
            shortwave_radiation_sum
        FROM read_parquet('{silver_glob}', hive_partitioning = true);
    """)

    # 1. Série Temporal Diária com Médias Móveis (7d / 30d) e Anomalia Térmica
    daily_out = outputs["daily_timeseries"].as_posix()
    con.execute(f"""
        COPY (
            WITH monthly_climatology AS (
                SELECT
                    city_slug,
                    month,
                    AVG(temperature_2m_mean) AS baseline_month_temp
                FROM silver_weather
                GROUP BY city_slug, month
            )
            SELECT
                s.date,
                s.year,
                s.month,
                s.season,
                s.city_slug,
                s.city_name,
                s.state,
                s.region,
                ROUND(s.temperature_2m_max, 2) AS temperature_2m_max,
                ROUND(s.temperature_2m_min, 2) AS temperature_2m_min,
                ROUND(s.temperature_2m_mean, 2) AS temperature_2m_mean,
                ROUND(s.temp_amplitude, 2) AS temp_amplitude,
                ROUND(s.precipitation_sum, 2) AS precipitation_sum,
                s.is_rainy_day,
                ROUND(s.wind_speed_10m_max, 2) AS wind_speed_10m_max,
                ROUND(s.shortwave_radiation_sum, 2) AS shortwave_radiation_sum,
                ROUND(
                    AVG(s.temperature_2m_mean) OVER (
                        PARTITION BY s.city_slug
                        ORDER BY s.date
                        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                    ), 2
                ) AS temp_ma_7d,
                ROUND(
                    AVG(s.temperature_2m_mean) OVER (
                        PARTITION BY s.city_slug
                        ORDER BY s.date
                        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
                    ), 2
                ) AS temp_ma_30d,
                ROUND(
                    SUM(s.precipitation_sum) OVER (
                        PARTITION BY s.city_slug
                        ORDER BY s.date
                        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
                    ), 2
                ) AS precip_rolling_30d,
                ROUND(s.temperature_2m_mean - c.baseline_month_temp, 2) AS temp_anomaly
            FROM silver_weather s
            INNER JOIN monthly_climatology c
                ON s.city_slug = c.city_slug AND s.month = c.month
            ORDER BY s.city_slug, s.date
        ) TO '{daily_out}' (FORMAT PARQUET, COMPRESSION SNAPPY);
    """)

    # 2. Resumo Mensal Agregado para Comparações Sazonais e Interanuais
    monthly_out = outputs["monthly_summary"].as_posix()
    con.execute(f"""
        COPY (
            WITH monthly_agg AS (
                SELECT
                    city_slug,
                    city_name,
                    state,
                    region,
                    year,
                    month,
                    ANY_VALUE(season) AS season,
                    MAKE_DATE(year, month, 1) AS year_month_date,
                    ROUND(AVG(temperature_2m_mean), 2) AS avg_temp_mean,
                    ROUND(MAX(temperature_2m_max), 2) AS max_temp_recorded,
                    ROUND(MIN(temperature_2m_min), 2) AS min_temp_recorded,
                    ROUND(AVG(temp_amplitude), 2) AS avg_temp_amplitude,
                    ROUND(SUM(precipitation_sum), 2) AS total_precipitation_mm,
                    ROUND(MAX(precipitation_sum), 2) AS max_daily_precipitation_mm,
                    SUM(CASE WHEN is_rainy_day THEN 1 ELSE 0 END) AS rainy_days_count,
                    ROUND(AVG(wind_speed_10m_max), 2) AS avg_wind_speed_max,
                    ROUND(AVG(shortwave_radiation_sum), 2) AS avg_solar_radiation
                FROM silver_weather
                GROUP BY city_slug, city_name, state, region, year, month
            ),
            climatology AS (
                SELECT
                    city_slug,
                    month,
                    AVG(avg_temp_mean) AS historical_month_avg_temp,
                    AVG(total_precipitation_mm) AS historical_month_avg_precip
                FROM monthly_agg
                GROUP BY city_slug, month
            )
            SELECT
                m.*,
                ROUND(m.avg_temp_mean - c.historical_month_avg_temp, 2) AS monthly_temp_anomaly,
                ROUND(m.total_precipitation_mm - c.historical_month_avg_precip, 2) AS monthly_precip_anomaly
            FROM monthly_agg m
            INNER JOIN climatology c
                ON m.city_slug = c.city_slug AND m.month = c.month
            ORDER BY m.city_slug, m.year, m.month
        ) TO '{monthly_out}' (FORMAT PARQUET, COMPRESSION SNAPPY);
    """)

    # 3. KPIs Executivos e Recordes Históricos por Cidade (usando ARG_MAX / ARG_MIN)
    kpis_out = outputs["city_kpis"].as_posix()
    con.execute(f"""
        COPY (
            SELECT
                city_slug,
                city_name,
                state,
                region,
                MIN(date) AS period_start,
                MAX(date) AS period_end,
                COUNT(*) AS total_days,
                ROUND(AVG(temperature_2m_mean), 2) AS overall_avg_temp,
                ROUND(AVG(temp_amplitude), 2) AS overall_avg_amplitude,
                ROUND(MAX(temperature_2m_max), 2) AS record_max_temp,
                ARG_MAX(date, temperature_2m_max) AS record_max_temp_date,
                ROUND(MIN(temperature_2m_min), 2) AS record_min_temp,
                ARG_MIN(date, temperature_2m_min) AS record_min_temp_date,
                ROUND(MAX(precipitation_sum), 2) AS record_max_precip_mm,
                ARG_MAX(date, precipitation_sum) AS record_max_precip_date,
                ROUND(SUM(precipitation_sum) / (COUNT(*) / 365.25), 1) AS avg_annual_precipitation_mm,
                ROUND(
                    SUM(CASE WHEN is_rainy_day THEN 1 ELSE 0 END) / (COUNT(*) / 365.25), 1
                ) AS avg_annual_rainy_days,
                ROUND(
                    AVG(CASE WHEN year >= 2023 THEN temperature_2m_mean END) -
                    AVG(CASE WHEN year <= 2019 THEN temperature_2m_mean END),
                    2
                ) AS recent_vs_early_temp_delta
            FROM silver_weather
            GROUP BY city_slug, city_name, state, region
            ORDER BY city_name
        ) TO '{kpis_out}' (FORMAT PARQUET, COMPRESSION SNAPPY);
    """)

    return outputs


def run_silver_to_gold() -> None:
    """Orquestra a criação das tabelas analíticas Gold via DuckDB."""
    silver_dir = SILVER_DIR / "weather_daily"
    if not silver_dir.exists() or not any(silver_dir.rglob("*.parquet")):
        raise FileNotFoundError(
            f"Nenhum arquivo Parquet encontrado em {silver_dir}. Execute bronze_to_silver primeiro."
        )

    silver_glob = (silver_dir / "**" / "*.parquet").as_posix()
    logger.info("Iniciando processamento Silver -> Gold com DuckDB...")

    with duckdb.connect(database=":memory:") as con:
        outputs = build_gold_tables(con, silver_glob)

        for table_name, file_path in outputs.items():
            row_count = con.execute(
                f"SELECT COUNT(*) FROM read_parquet('{file_path.as_posix()}')"
            ).fetchone()[0]
            size_kb = file_path.stat().st_size / 1024
            logger.info(
                "Tabela Gold '%s' gerada: %s (%d linhas | %.1f KB)",
                table_name,
                file_path.name,
                row_count,
                size_kb,
            )

    logger.info("Camada Gold concluída com sucesso.")


if __name__ == "__main__":
    run_silver_to_gold()