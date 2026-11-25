from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from components.charts import (
    plot_cities_comparison,
    plot_daily_temperature_series,
    plot_seasonality_profile,
    plot_thermal_anomaly_bars,
)

GOLD_DIR = Path(__file__).resolve().parents[1] / "data" / "gold"

st.set_page_config(
    page_title="Climate Data Lake | Análise de Séries Temporais",
    page_icon="🌦️",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def load_gold_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Consulta as tabelas Parquet da camada Gold utilizando DuckDB in-process."""
    daily_path = (GOLD_DIR / "gold_daily_timeseries.parquet").as_posix()
    monthly_path = (GOLD_DIR / "gold_monthly_summary.parquet").as_posix()
    kpis_path = (GOLD_DIR / "gold_city_kpis.parquet").as_posix()

    with duckdb.connect(database=":memory:") as con:
        daily_df = con.execute(f"SELECT * FROM read_parquet('{daily_path}')").df()
        monthly_df = con.execute(f"SELECT * FROM read_parquet('{monthly_path}')").df()
        kpis_df = con.execute(f"SELECT * FROM read_parquet('{kpis_path}')").df()

    daily_df["date"] = pd.to_datetime(daily_df["date"])
    monthly_df["year_month_date"] = pd.to_datetime(monthly_df["year_month_date"])
    return daily_df, monthly_df, kpis_df


def build_dynamic_conclusions(
    city_name: str,
    city_kpi: pd.Series,
    filtered_daily: pd.DataFrame,
    filtered_monthly: pd.DataFrame,
    year_range: tuple[int, int],
) -> list[str]:
    """Gera conclusões analíticas textuais a partir do recorte filtrado."""
    insights: list[str] = []

    # 1. Tendência térmica e extremos no período selecionado
    yearly_temp = filtered_daily.groupby("year")["temperature_2m_mean"].mean()
    hottest_year = int(yearly_temp.idxmax())
    coldest_year = int(yearly_temp.idxmin())
    delta_decade = float(city_kpi["recent_vs_early_temp_delta"])
    trend_word = "aquecimento" if delta_decade > 0 else "resfriamento"

    insights.append(
        f"**Tendência Térmica ({year_range[0]}–{year_range[1]}):** Em **{city_name}**, "
        f"o ano mais quente do recorte foi **{hottest_year}** (média de **{yearly_temp[hottest_year]:.1f} °C**), "
        f"enquanto **{coldest_year}** registrou a menor média (**{yearly_temp[coldest_year]:.1f} °C**). "
        f"Comparando o triênio recente (2023+) com o início da série (2016–2019), observa-se um "
        f"**{trend_word} médio de {delta_decade:+.2f} °C**."
    )

    # 2. Concentração pluviométrica por estação
    season_precip = (
        filtered_monthly.groupby("season")["total_precipitation_mm"]
        .sum()
        .sort_values(ascending=False)
    )
    total_precip = season_precip.sum()
    if total_precip > 0:
        wettest_season = season_precip.index[0]
        wettest_share = (season_precip.iloc[0] / total_precip) * 100
        driest_season = season_precip.index[-1]
        driest_share = (season_precip.iloc[-1] / total_precip) * 100

        insights.append(
            f"**Sazonalidade das Chuvas:** O regime hídrico é fortemente concentrado no **{wettest_season}**, "
            f"que responde por **{wettest_share:.1f}%** de todo o volume precipitado no período, "
            f"contrastando com o **{driest_season}** (**{driest_share:.1f}%** do total)."
        )

    # 3. Frequência de anomalias positivas recentes
    positive_anomalies = (filtered_monthly["monthly_temp_anomaly"] > 0).mean() * 100
    max_amp_day = filtered_daily.loc[filtered_daily["temp_amplitude"].idxmax()]
    insights.append(
        f"**Anomalias e Amplitude Térmica:** **{positive_anomalies:.0f}%** dos meses analisados "
        f"ficaram acima da normal climatológica histórica. A maior variação térmica em um único dia "
        f"ocorreu em **{max_amp_day['date'].strftime('%d/%m/%Y')}**, atingindo amplitude de "
        f"**{max_amp_day['temp_amplitude']:.1f} °C**."
    )

    return insights


def main() -> None:
    if not (GOLD_DIR / "gold_daily_timeseries.parquet").exists():
        st.error(
            "Arquivos da camada Gold não encontrados em `data/gold/`. "
            "Execute o pipeline ETL (`fetch_weather`, `bronze_to_silver`, `silver_to_gold`) primeiro."
        )
        st.stop()

    daily_df, monthly_df, kpis_df = load_gold_data()

    # Sidebar — Controles interativos
    st.sidebar.header("Filtros do Data Lake")
    city_options = kpis_df["city_name"].tolist()
    selected_city = st.sidebar.selectbox("Capital Principal", options=city_options, index=0)

    min_year = int(daily_df["year"].min())
    max_year = int(daily_df["year"].max())
    year_range = st.sidebar.slider(
        "Janela Temporal (Anos)",
        min_value=min_year,
        max_value=max_year,
        value=(min_year, max_year),
    )

    compare_cities = st.sidebar.multiselect(
        "Cidades para Comparação Regional",
        options=city_options,
        default=city_options[:3],
    )

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "**Arquitetura:** Open-Meteo API → Bronze (JSON) → Silver (Parquet Particionado) "
        "→ Gold (DuckDB SQL) → Streamlit"
    )

    # Filtragem dos dados
    city_kpi = kpis_df[kpis_df["city_name"] == selected_city].iloc[0]
    filtered_daily = daily_df[
        (daily_df["city_name"] == selected_city)
        & (daily_df["year"].between(year_range[0], year_range[1]))
    ]
    filtered_monthly = monthly_df[
        (monthly_df["city_name"] == selected_city)
        & (monthly_df["year"].between(year_range[0], year_range[1]))
    ]

    # Cabeçalho
    st.title("🌦️ Data Lake Climático — Análise Histórica e Séries Temporais")
    st.markdown(
        f"Explorando **{city_kpi['total_days']:,}** registros meteorológicos diários de "
        f"**{selected_city} ({city_kpi['state']})** — Região {city_kpi['region']}."
    )

    # Linha de KPIs Executivos
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric(
        "Temp. Média Histórica",
        f"{city_kpi['overall_avg_temp']:.1f} °C",
        delta=f"{city_kpi['recent_vs_early_temp_delta']:+.2f} °C (2023+ vs 16–19)",
    )
    col2.metric(
        "Recorde de Calor",
        f"{city_kpi['record_max_temp']:.1f} °C",
        delta=pd.to_datetime(city_kpi["record_max_temp_date"]).strftime("%d/%m/%Y"),
        delta_color="off",
    )
    col3.metric(
        "Recorde de Frio",
        f"{city_kpi['record_min_temp']:.1f} °C",
        delta=pd.to_datetime(city_kpi["record_min_temp_date"]).strftime("%d/%m/%Y"),
        delta_color="off",
    )
    col4.metric(
        "Chuva Média Anual",
        f"{city_kpi['avg_annual_precipitation_mm']:.0f} mm",
        delta=f"{city_kpi['avg_annual_rainy_days']:.0f} dias chuvosos/ano",
        delta_color="off",
    )
    col5.metric(
        "Maior Chuva em 24h",
        f"{city_kpi['record_max_precip_mm']:.1f} mm",
        delta=pd.to_datetime(city_kpi["record_max_precip_date"]).strftime("%d/%m/%Y"),
        delta_color="off",
    )

    st.markdown("---")

    # Abas Analíticas
    tab1, tab2, tab3 = st.tabs(
        [
            "📈 Séries Temporais & Anomalias",
            "🌧️ Sazonalidade & Precipitação",
            "🌎 Comparativo Entre Capitais",
        ]
    )

    with tab1:
        st.plotly_chart(
            plot_daily_temperature_series(filtered_daily, selected_city),
            use_container_width=True,
        )
        st.plotly_chart(
            plot_thermal_anomaly_bars(filtered_monthly, selected_city),
            use_container_width=True,
        )

    with tab2:
        st.plotly_chart(
            plot_seasonality_profile(filtered_monthly, selected_city),
            use_container_width=True,
        )

        season_table = (
            filtered_monthly.groupby("season", as_index=False)
            .agg(
                temp_media=("avg_temp_mean", "mean"),
                amplitude_media=("avg_temp_amplitude", "mean"),
                chuva_total_mm=("total_precipitation_mm", "sum"),
                dias_chuvosos=("rainy_days_count", "sum"),
                radiacao_solar=("avg_solar_radiation", "mean"),
            )
            .round(1)
        )
        st.subheader("Consolidado por Estação do Ano")
        st.dataframe(season_table, use_container_width=True, hide_index=True)

    with tab3:
        if not compare_cities:
            st.info("Selecione ao menos uma cidade na barra lateral para comparar.")
        else:
            comp_daily = daily_df[
                (daily_df["city_name"].isin(compare_cities))
                & (daily_df["year"].between(year_range[0], year_range[1]))
            ]
            st.plotly_chart(
                plot_cities_comparison(
                    comp_daily,
                    metric_col="temp_ma_30d",
                    metric_label="Temperatura Média Móvel 30d (°C)",
                ),
                use_container_width=True,
            )
            st.plotly_chart(
                plot_cities_comparison(
                    comp_daily,
                    metric_col="precip_rolling_30d",
                    metric_label="Chuva Acumulada Móvel 30d (mm)",
                ),
                use_container_width=True,
            )

            st.subheader("Tabela Comparativa de Indicadores Históricos")
            comp_kpis = kpis_df[kpis_df["city_name"].isin(compare_cities)][
                [
                    "city_name",
                    "region",
                    "overall_avg_temp",
                    "overall_avg_amplitude",
                    "record_max_temp",
                    "record_min_temp",
                    "avg_annual_precipitation_mm",
                    "recent_vs_early_temp_delta",
                ]
            ]
            st.dataframe(comp_kpis, use_container_width=True, hide_index=True)

    # Conclusões Textuais Dinâmicas
    st.markdown("---")
    st.subheader(f"📝 Conclusões Analíticas — {selected_city}")
    conclusions = build_dynamic_conclusions(
        selected_city, city_kpi, filtered_daily, filtered_monthly, year_range
    )
    for item in conclusions:
        st.markdown(f"- {item}")


if __name__ == "__main__":
    main()