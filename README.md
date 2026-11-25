# 🌦️ Climate Data Lake — Time Series & Climatological Analytics

> 🇺🇸 **English** | 🇧🇷 [Leia em Português](README.pt-BR.md)

🔗 **Live Interactive Dashboard:** [mirelly-climate-data-lake.streamlit.app](https://mirelly-climate-data-lake.streamlit.app)

An end-to-end **Data Engineering and Time Series Analytics** pipeline built on a **Medallion Architecture** (`Bronze → Silver → Gold`) using **Apache Parquet** columnar storage, **DuckDB** in-process SQL analytics, and an interactive **Streamlit + Plotly** data application.

---

## 1. Analytical Problem & Objectives

Climate variability across Brazil's distinct geographic regions directly impacts agriculture, urban infrastructure, and energy planning. This project consolidates over a decade of daily meteorological observations (**2016–2026**) across 5 Brazilian state capitals (**Belo Horizonte, São Paulo, Rio de Janeiro, Manaus, and Porto Alegre**) to answer **3 core analytical questions**:

1. **Long-Term Thermal Trends:** How have average temperatures shifted between the early baseline period (`2016–2019`) and recent years (`2023+`) across each climate zone?
2. **Climatological Anomalies:** How frequently do monthly and daily temperatures deviate from each capital's historical baseline?
3. **Seasonal Regimes & Extremes:** How are precipitation volumes, diurnal temperature amplitudes, and solar radiation distributed across Southern Hemisphere seasons?

---

## 2. Solution Architecture

The pipeline decouples raw API ingestion, partitioned columnar storage, and serverless SQL transformations before serving lightweight analytical tables to the cloud dashboard:

```text
┌─────────────────────────────────────────┐
│   Open-Meteo Historical Weather API     │
│ • Daily temperature (min, mean, max)    │
│ • Precipitation, wind speed & radiation │
└────────────────────┬────────────────────┘
                     ▼
┌─────────────────────────────────────────┐
│   Python Ingestion Layer                │
│ • Exponential Backoff + Jitter retries  │
│ • Idempotent local checkpointing        │
│ • UTC metadata & source traceability    │
└────────────────────┬────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   Parquet Data Lake (Medallion Layers)                  │
│                                                                         │
│  ┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐  │
│  │   BRONZE Layer    │   │   SILVER Layer    │   │    GOLD Layer     │  │
│  │  Raw JSON + Meta  │──▶│  Hive-Partitioned │──▶│  DuckDB SQL OLAP  │  │
│  │  (Audit & Replay) │   │  Parquet (Snappy) │   │  Rolling & KPIs   │  │
│  └───────────────────┘   └───────────────────┘   └─────────┬─────────┘  │
└────────────────────────────────────────────────────────────┼────────────┘
                                                             ▼
                                           ┌───────────────────────────────┐
                                           │  Streamlit + Plotly Data App  │
                                           │ • Interactive time series     │
                                           │ • Dynamic automated insights  │
                                           └───────────────────────────────┘
```

- **Bronze Layer (`data/bronze/`):** Persists raw API JSON payloads wrapped with UTC ingestion timestamps and geographic metadata for full auditability and schema replay.
- **Silver Layer (`data/silver/`):** Standardizes types, deduplicates records, computes diurnal thermal amplitude and Southern Hemisphere seasons, and writes **Snappy-compressed Parquet** files using Hive partitioning (`city_slug=.../year=...`).
- **Gold Layer (`data/gold/`):** Executes analytical SQL queries in **DuckDB** directly over partitioned Parquet files—leveraging *Partition Pruning*, *Predicate Pushdown*, and *Column Projection*—to materialize 7-day/30-day rolling averages (`Window Functions`) and exact historical extremes (`ARG_MAX` / `ARG_MIN`).

---

## 3. Tech Stack

- **Ingestion & Processing:** Python 3.11+, `Requests`, `Pandas`, `PyArrow`
- **Data Lake Storage:** Apache Parquet (Snappy compression & Hive-style partitioning)
- **Analytical SQL Engine:** `DuckDB` (in-process vectorized OLAP)
- **Data Quality & Testing:** `Pytest` (unit transformation tests + Gold layer physical integrity checks)
- **Visualization & Deployment:** `Streamlit`, `Plotly`, hosted on **Streamlit Community Cloud**

---

## 4. Engineering & Data Quality Highlights

1. **Resilient API Extraction (`Exponential Backoff + Jitter`):** Handles `HTTP 429` rate limits gracefully with randomized exponential wait intervals (`15s → 30s → 60s + jitter`) and skips already-extracted cities via idempotent checkpointing.
2. **Columnar Optimization & Zero-Server Deployment:** Partitioning the Silver layer by `city_slug` and `year` allows DuckDB to prune irrelevant directories at scan time, while compact Gold Parquet files (`< 1 MB` total) enable instant, zero-database cloud deployment.
3. **Window Functions & Climatological Baselines:** Uses SQL `OVER (PARTITION BY ... ROWS BETWEEN ...)` clauses to compute 7-day and 30-day moving averages alongside monthly thermal anomalies relative to each city's multi-year baseline.
4. **Automated Data Quality Gates:** `Pytest` validates Southern Hemisphere seasonal classification, duplicate resolution, non-null rolling metrics, and physical bounds (`temperature_2m_max >= temperature_2m_min` and non-negative precipitation).

---

## 5. Repository Structure

```text
climate-data-lake/
├── app/
│   ├── components/
│   │   └── charts.py           # Reusable interactive time-series charts (Plotly)
│   └── main.py                 # Streamlit dashboard, KPIs & dynamic text conclusions
├── data/
│   ├── bronze/                 # Raw JSON snapshots (gitignored)
│   ├── silver/                 # Hive-partitioned Parquet dataset (gitignored)
│   └── gold/                   # Aggregated analytical Parquet tables (versioned)
├── src/
│   ├── ingestion/
│   │   └── fetch_weather.py    # Resilient Open-Meteo historical extractor
│   ├── processing/
│   │   ├── bronze_to_silver.py # Cleaning, typing & partitioned Parquet writer
│   │   └── silver_to_gold.py   # DuckDB SQL transformations & Gold aggregations
│   └── utils/
│       └── config.py           # Global paths, date windows & city coordinates
├── tests/
│   └── test_pipeline.py        # Unit & Gold layer data quality test suite
├── pyproject.toml              # Pytest path configuration
├── requirements.txt            # Python dependencies
├── README.md                   # English documentation
└── README.pt-BR.md             # Portuguese documentation
```

---

## 6. Quickstart

### 1. Clone and set up the virtual environment
```powershell
git clone [https://github.com/MirellyAlvarenga/climate-data-lake.git](https://github.com/MirellyAlvarenga/climate-data-lake.git)
cd climate-data-lake

python -m venv .venv
.\.venv\Scripts\Activate.ps1  # On Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. Run the end-to-end Data Lake pipeline (`Bronze → Silver → Gold`)
```powershell
python -m src.ingestion.fetch_weather
python -m src.processing.bronze_to_silver
python -m src.processing.silver_to_gold
```

### 3. Run data quality tests and launch the dashboard
```powershell
pytest -v
streamlit run app/main.py
```