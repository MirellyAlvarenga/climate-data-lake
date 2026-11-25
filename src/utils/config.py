from datetime import date, timedelta
from pathlib import Path

# Diretórios base do projeto
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"

# Endpoint da Open-Meteo Historical Weather API (gratuita, sem API Key)
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Janela histórica: 10+ anos até 7 dias atrás (respeita o atraso de consolidação da reanálise ERA5)
START_DATE = "2016-01-01"
END_DATE = (date.today() - timedelta(days=7)).isoformat()

# Variáveis meteorológicas diárias
DAILY_VARIABLES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "rain_sum",
    "wind_speed_10m_max",
    "shortwave_radiation_sum",
]

# Cidades monitoradas (coordenadas geográficas)
CITIES = {
    "belo_horizonte": {
        "name": "Belo Horizonte",
        "state": "MG",
        "region": "Sudeste",
        "latitude": -19.9167,
        "longitude": -43.9345,
    },
    "sao_paulo": {
        "name": "São Paulo",
        "state": "SP",
        "region": "Sudeste",
        "latitude": -23.5505,
        "longitude": -46.6333,
    },
    "rio_de_janeiro": {
        "name": "Rio de Janeiro",
        "state": "RJ",
        "region": "Sudeste",
        "latitude": -22.9068,
        "longitude": -43.1729,
    },
    "manaus": {
        "name": "Manaus",
        "state": "AM",
        "region": "Norte",
        "latitude": -3.1190,
        "longitude": -60.0217,
    },
    "porto_alegre": {
        "name": "Porto Alegre",
        "state": "RS",
        "region": "Sul",
        "latitude": -30.0346,
        "longitude": -51.2177,
    },
}