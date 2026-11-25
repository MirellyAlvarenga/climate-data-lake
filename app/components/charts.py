import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

MONTH_NAMES_PT = {
    1: "Jan",
    2: "Fev",
    3: "Mar",
    4: "Abr",
    5: "Mai",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Set",
    10: "Out",
    11: "Nov",
    12: "Dez",
}


def plot_daily_temperature_series(df: pd.DataFrame, city_name: str) -> go.Figure:
    """Série temporal diária com faixa min/max e médias móveis de 7d e 30d."""
    fig = go.Figure()

    # Faixa entre temperatura mínima e máxima diária
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["temperature_2m_max"],
            mode="lines",
            line=dict(width=0),
            name="Máxima Diária",
            showlegend=False,
            hovertemplate="Máx: %{y:.1f} °C<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["temperature_2m_min"],
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(100, 149, 237, 0.16)",
            name="Amplitude (Mín–Máx)",
            hovertemplate="Mín: %{y:.1f} °C<extra></extra>",
        )
    )

    # Média móvel de 7 dias
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["temp_ma_7d"],
            mode="lines",
            line=dict(color="rgba(59, 130, 246, 0.55)", width=1.3),
            name="Média Móvel 7d",
            hovertemplate="MM 7d: %{y:.1f} °C<extra></extra>",
        )
    )

    # Média móvel de 30 dias (tendência suavizada)
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["temp_ma_30d"],
            mode="lines",
            line=dict(color="#ef4444", width=2.4),
            name="Média Móvel 30d",
            hovertemplate="MM 30d: %{y:.1f} °C<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"Evolução Térmica Diária e Médias Móveis — {city_name}",
        xaxis_title="Data",
        yaxis_title="Temperatura (°C)",
        hovermode="x unified",
        template="plotly_white",
        height=430,
        margin=dict(l=20, r=20, t=55, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def plot_thermal_anomaly_bars(monthly_df: pd.DataFrame, city_name: str) -> go.Figure:
    """Gráfico de barras divergentes mostrando anomalias mensais frente à climatologia."""
    colors = [
        "#dc2626" if val >= 0 else "#2563eb"
        for val in monthly_df["monthly_temp_anomaly"]
    ]

    fig = go.Figure(
        go.Bar(
            x=monthly_df["year_month_date"],
            y=monthly_df["monthly_temp_anomaly"],
            marker_color=colors,
            name="Anomalia Térmica",
            hovertemplate=(
                "Mês: %{x|%Y-%m}<br>"
                "Desvio vs. Média Histórica: %{y:+.2f} °C<extra></extra>"
            ),
        )
    )

    fig.add_hline(y=0, line_dash="dash", line_color="#64748b", line_width=1)

    fig.update_layout(
        title=f"Anomalia Térmica Mensal (Desvio da Normal Climatológica) — {city_name}",
        xaxis_title="Mês / Ano",
        yaxis_title="Anomalia (°C)",
        template="plotly_white",
        height=370,
        margin=dict(l=20, r=20, t=55, b=20),
    )
    return fig


def plot_seasonality_profile(monthly_df: pd.DataFrame, city_name: str) -> go.Figure:
    """Climatologia mensal (Jan–Dez) cruzando precipitação acumulada e temperatura média."""
    climatology = (
        monthly_df.groupby("month", as_index=False)
        .agg(
            avg_precip=("total_precipitation_mm", "mean"),
            avg_temp=("avg_temp_mean", "mean"),
            avg_rainy_days=("rainy_days_count", "mean"),
        )
        .sort_values("month")
    )
    climatology["month_label"] = climatology["month"].map(MONTH_NAMES_PT)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            x=climatology["month_label"],
            y=climatology["avg_precip"],
            name="Precipitação Média (mm)",
            marker_color="rgba(37, 99, 235, 0.72)",
            hovertemplate="Chuva Média: %{y:.1f} mm<extra></extra>",
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=climatology["month_label"],
            y=climatology["avg_temp"],
            name="Temperatura Média (°C)",
            mode="lines+markers",
            line=dict(color="#f97316", width=3),
            marker=dict(size=8),
            hovertemplate="Temp. Média: %{y:.1f} °C<extra></extra>",
        ),
        secondary_y=True,
    )

    fig.update_layout(
        title=f"Regime Sazonal: Chuva vs. Temperatura por Mês — {city_name}",
        template="plotly_white",
        height=410,
        hovermode="x unified",
        margin=dict(l=20, r=20, t=55, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_yaxes(title_text="Precipitação Mensal Média (mm)", secondary_y=False)
    fig.update_yaxes(title_text="Temperatura Média (°C)", secondary_y=True)
    return fig


def plot_cities_comparison(
    daily_df: pd.DataFrame, metric_col: str, metric_label: str
) -> go.Figure:
    """Compara a trajetória suavizada (média móvel 30d) entre múltiplas capitais."""
    fig = go.Figure()

    for city_name, group in daily_df.groupby("city_name"):
        fig.add_trace(
            go.Scatter(
                x=group["date"],
                y=group[metric_col],
                mode="lines",
                name=city_name,
                line=dict(width=2),
                hovertemplate=f"{city_name}: %{{y:.1f}}<extra></extra>",
            )
        )

    fig.update_layout(
        title=f"Comparativo Inter-Regional — {metric_label}",
        xaxis_title="Data",
        yaxis_title=metric_label,
        hovermode="x unified",
        template="plotly_white",
        height=430,
        margin=dict(l=20, r=20, t=55, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig