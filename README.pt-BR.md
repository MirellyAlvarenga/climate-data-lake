# 🌦️ Climate Data Lake — Séries Temporais & Análise Climática

> 🇺🇸 [Read in English](README.md) | 🇧🇷 **Português**

🔗 **Dashboard Interativo:** [mirelly-climate-data-lake.streamlit.app](https://mirelly-climate-data-lake.streamlit.app)

Pipeline end-to-end de **Engenharia e Análise de Dados** meteorológicos construído sobre arquitetura **Medalhão** (`Bronze → Silver → Gold`) com armazenamento colunar em **Apache Parquet**, processamento analítico *in-process* via **DuckDB** e relatório interativo em **Streamlit + Plotly**.

---

## 1. Problema Analítico & Objetivos

A variabilidade climática entre as diferentes regiões do Brasil impacta diretamente o planejamento agrícola, energético e urbano. Este projeto consolida mais de uma década de séries históricas diárias (**2016–2026**) de 5 capitais brasileiras de distintos regimes climáticos (**Belo Horizonte, São Paulo, Rio de Janeiro, Manaus e Porto Alegre**) para responder a **3 perguntas analíticas centrais**:

1. **Tendência Térmica de Longo Prazo:** Como as temperaturas médias evoluíram entre o período inicial da série (`2016–2019`) e o triênio recente (`2023+`) em cada capital?
2. **Anomalias Climatológicas:** Com que frequência as temperaturas mensais e diárias superam a normal histórica de cada cidade?
3. **Regimes Sazonais & Extremos:** Como o volume de chuvas, a amplitude térmica diária e a radiação solar se distribuem entre as estações do Hemisfério Sul?

---

## 2. Arquitetura da Solução

O pipeline desacopla a extração bruta da API, o armazenamento colunar particionado e as transformações SQL sem servidor antes de servir tabelas analíticas leves para o dashboard na nuvem:

```text
┌─────────────────────────────────────────┐
│   Open-Meteo Historical Weather API     │
│ • Temperatura diária (mín, média, máx)  │
│ • Precipitação, vento e radiação solar  │
└────────────────────┬────────────────────┘
                     ▼
┌─────────────────────────────────────────┐
│   Camada de Ingestão em Python          │
│ • Retries com Exponential Backoff+Jitter│
│ • Checkpointing local idempotente       │
│ • Metadados UTC de rastreabilidade      │
└────────────────────┬────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  Data Lake em Parquet (Camadas Medalhão)                │
│                                                                         │
│  ┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐  │
│  │   Camada BRONZE   │   │   Camada SILVER   │   │    Camada GOLD    │  │
│  │ JSON Bruto + Meta │──▶│ Parquet Partic.   │──▶│  DuckDB SQL OLAP  │  │
│  │ (Auditoria/Replay)│   │ Hive + Snappy     │   │ Médias Móveis/KPIs│  │
│  └───────────────────┘   └───────────────────┘   └─────────┬─────────┘  │
└────────────────────────────────────────────────────────────┼────────────┘
                                                             ▼
                                           ┌───────────────────────────────┐
                                           │  App Streamlit + Plotly       │
                                           │ • Séries temporais interativas│
                                           │ • Conclusões textuais dinâm.  │
                                           └───────────────────────────────┘
```

- **Camada Bronze (`data/bronze/`):** Persiste os payloads JSON brutos envelopados com timestamps UTC de ingestão e metadados geográficos, garantindo auditoria completa e reprocessamento.
- **Camada Silver (`data/silver/`):** Padroniza tipos, remove duplicatas, calcula amplitude térmica diária e estações do Hemisfério Sul, gravando arquivos **Parquet comprimidos em Snappy** com particionamento estilo Hive (`city_slug=.../year=...`).
- **Camada Gold (`data/gold/`):** Executa consultas SQL analíticas no **DuckDB** diretamente sobre os arquivos particionados — aproveitando *Partition Pruning*, *Predicate Pushdown* e *Column Projection* — para materializar médias móveis de 7d/30d (`Window Functions`) e recordes históricos exatos (`ARG_MAX` / `ARG_MIN`).

---

## 3. Stack Tecnológica

- **Ingestão & Processamento:** Python 3.11+, `Requests`, `Pandas`, `PyArrow`
- **Armazenamento Data Lake:** Apache Parquet (compressão Snappy e particionamento Hive)
- **Motor Analítico SQL:** `DuckDB` (OLAP vetorizado *in-process*)
- **Qualidade de Dados & Testes:** `Pytest` (testes unitários de transformação e integridade física da camada Gold)
- **Visualização & Deploy:** `Streamlit`, `Plotly`, publicado no **Streamlit Community Cloud**

---

## 4. Destaques de Engenharia & Qualidade de Dados

1. **Extração Resiliente (`Exponential Backoff + Jitter`):** Trata limites de requisição (`HTTP 429`) com intervalos exponenciais aleatorizados (`15s → 30s → 60s + jitter`) e evita reprocessamento desnecessário via *checkpointing* idempotente.
2. **Otimização Colunar & Deploy Sem Servidor:** O particionamento da Silver por `city_slug` e `year` permite ao DuckDB podar diretórios irrelevantes na leitura, enquanto os Parquets compactos da Gold (`< 1 MB` no total) viabilizam deploy gratuito na nuvem sem banco externo.
3. **Window Functions & Linhas de Base Climatológicas:** Utiliza cláusulas SQL `OVER (PARTITION BY ... ROWS BETWEEN ...)` para calcular médias móveis de 7 e 30 dias e anomalias térmicas em relação à média histórica mensal de cada capital.
4. **Gates Automatizados de Qualidade:** O `Pytest` valida o mapeamento sazonal do Hemisfério Sul, deduplicação, ausência de nulos nas janelas móveis e limites físicos (`temperature_2m_max >= temperature_2m_min` e precipitação não negativa).

---

## 5. Estrutura do Repositório

```text
climate-data-lake/
├── app/
│   ├── components/
│   │   └── charts.py           # Gráficos interativos de séries temporais (Plotly)
│   └── main.py                 # Dashboard Streamlit, KPIs e conclusões dinâmicas
├── data/
│   ├── bronze/                 # JSONs brutos (ignorado no Git)
│   ├── silver/                 # Parquet particionado por cidade/ano (ignorado no Git)
│   └── gold/                   # Tabelas analíticas finais em Parquet (versionadas)
├── src/
│   ├── ingestion/
│   │   └── fetch_weather.py    # Extrator resiliente da Open-Meteo API
│   ├── processing/
│   │   ├── bronze_to_silver.py # Limpeza, tipagem e escrita Parquet particionada
│   │   └── silver_to_gold.py   # Transformações SQL DuckDB e agregações Gold
│   └── utils/
│       └── config.py           # Caminhos globais, janelas de data e coordenadas
├── tests/
│   └── test_pipeline.py        # Suíte de testes unitários e de qualidade (Pytest)
├── pyproject.toml              # Configuração de paths do Pytest
├── requirements.txt            # Dependências Python
├── README.md                   # Documentação em Inglês
└── README.pt-BR.md             # Documentação em Português
```

---

## 6. Como Executar Localmente

### 1. Clonar e configurar o ambiente virtual
```powershell
git clone [https://github.com/MirellyAlvarenga/climate-data-lake.git](https://github.com/MirellyAlvarenga/climate-data-lake.git)
cd climate-data-lake

python -m venv .venv
.\.venv\Scripts\Activate.ps1  # No Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. Executar o pipeline completo (`Bronze → Silver → Gold`)
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