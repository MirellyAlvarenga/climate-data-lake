# 🌦️ Climate Data Lake — Séries Temporais & Análise Climática

Pipeline end-to-end de Engenharia e Análise de Dados meteorológicos construído sobre arquitetura **Medalhão (Bronze, Silver e Gold)** com armazenamento colunar em **Apache Parquet**, processamento analítico *in-process* via **DuckDB** e relatório interativo em **Streamlit + Plotly**.

🔗 **Dashboard Interativo:** *https://mirelly-climate-data-lake.streamlit.app*

---

## 🎯 Objetivo do Projeto

Consolidar mais de uma década de séries históricas diárias (2016–2026) de 5 capitais brasileiras de diferentes regiões climáticas (**Belo Horizonte, São Paulo, Rio de Janeiro, Manaus e Porto Alegre**) para responder a perguntas analíticas sobre:

- **Tendência térmica de longo prazo:** comparação entre o início da série (2016–2019) e o período recente (2023+).
- **Anomalias climatológicas:** desvios mensais e diários em relação à normal histórica de cada capital.
- **Regimes sazonais:** distribuição pluviométrica, amplitude térmica e radiação solar por estação do ano.

---

## 🏗️ Arquitetura do Data Lake

1. **Extração (`src/ingestion/fetch_weather.py`):** Coleta séries diárias via **Open-Meteo Historical Weather API** com *checkpointing* idempotente e tratamento de limite de requisições (`HTTP 429`) utilizando *Exponential Backoff + Jitter*.
2. **Camada Bronze (`data/bronze/`):** Persistência dos payloads JSON brutos envelopados com metadados de rastreabilidade (timestamp UTC de ingestão e coordenadas), garantindo auditoria e reprocessamento.
3. **Camada Silver (`src/processing/bronze_to_silver.py`):** Limpeza, tipagem estrita, deduplicação, cálculo de amplitude térmica e gravação em **Apache Parquet (compressão Snappy)** com particionamento estilo Hive (`city_slug=.../year=...`).
4. **Camada Gold (`src/processing/silver_to_gold.py`):** Consultas SQL analíticas executadas no **DuckDB** diretamente sobre os arquivos particionados (aproveitando *Partition Pruning*, *Predicate Pushdown* e *Column Projection*), gerando tabelas agregadas com *Window Functions* (médias móveis de 7d/30d) e funções `ARG_MAX` / `ARG_MIN` para recordes históricos.
5. **Visualização (`app/main.py`):** Dashboard interativo em **Streamlit** e **Plotly** que consulta a camada Gold via DuckDB e gera conclusões textuais dinâmicas conforme os filtros aplicados.

---

## 📂 Estrutura do Repositório

```text
climate-data-lake/
├── app/
│   ├── components/
│   │   └── charts.py           # Gráficos interativos de séries temporais (Plotly)
│   └── main.py                 # Aplicação Streamlit, KPIs e conclusões dinâmicas
├── data/
│   ├── bronze/                 # JSONs brutos (ignorado no Git)
│   ├── silver/                 # Parquet particionado por cidade/ano (ignorado no Git)
│   └── gold/                   # Tabelas analíticas finais em Parquet (versionadas)
├── src/
│   ├── ingestion/
│   │   └── fetch_weather.py    # Extrator resiliente da Open-Meteo API
│   ├── processing/
│   │   ├── bronze_to_silver.py # Padronização e escrita Parquet particionada
│   │   └── silver_to_gold.py   # Modelagem analítica e agregações via DuckDB
│   └── utils/
│       └── config.py           # Parâmetros globais e coordenadas das capitais
├── tests/
│   └── test_pipeline.py        # Testes unitários e de qualidade de dados (Pytest)
├── pyproject.toml              # Configuração do Pytest e pythonpath
├── requirements.txt
└── README.md
```

---

## 🚀 Como Executar Localmente

### 1. Clonar e configurar o ambiente virtual (Windows PowerShell)

```powershell
git clone [https://github.com/SEU-USUARIO/climate-data-lake.git](https://github.com/SEU-USUARIO/climate-data-lake.git)
cd climate-data-lake

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. Executar o pipeline completo (Bronze → Silver → Gold)

```powershell
python -m src.ingestion.fetch_weather
python -m src.processing.bronze_to_silver
python -m src.processing.silver_to_gold
```

### 3. Validar qualidade dos dados e abrir o dashboard

```powershell
pytest -v
streamlit run app/main.py
```

---

## 🛠️ Stack Tecnológica

| Camada / Função | Tecnologia |
| :--- | :--- |
| **Linguagem** | Python 3.11+ |
| **Armazenamento Data Lake** | Apache Parquet (PyArrow + Snappy) |
| **Motor Analítico SQL** | DuckDB (*in-process* OLAP) |
| **Manipulação & API** | Pandas, Requests |
| **Visualização & App** | Streamlit, Plotly |
| **Qualidade & Testes** | Pytest |
