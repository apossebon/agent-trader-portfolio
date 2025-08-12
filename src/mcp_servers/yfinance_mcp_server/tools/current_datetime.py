from datetime import datetime
from zoneinfo import ZoneInfo   # disponível a partir do Python 3.9

def get_current_datetime(tz: str = "America/Sao_Paulo") -> str:
    
    try:
        now = datetime.now(ZoneInfo(tz))
        print(f"Data/hora atual em {tz}: {now.strftime("%Y-%m-%d %H:%M:%S")}")
        # Formata a data/hora no formato desejado
        # Exemplo: "2023-10-01 12:00:00 (America/Sao_Paulo)"
        return now.strftime("%Y-%m-%d %H:%M:%S") + f" ({tz})"
    except Exception as e:
        return f"Erro ao obter data/hora para o fuso '{tz}': {e}"