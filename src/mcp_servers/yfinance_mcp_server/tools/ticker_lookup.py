# tools/ticker_lookup.py

import requests

def find_ticker(company_name: str) -> str:
    """
    Busca o ticker no Yahoo Finance com base no nome da empresa.
    Retorna o primeiro resultado da B3 (.SA), se disponível.
    """
    print(f"Buscando ticker para '{company_name}'...")
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={company_name}"
        headers = {"User-Agent": "Mozilla/5.0"}  # evita bloqueios do Yahoo
        response = requests.get(url, headers=headers)
        results = response.json()

        if "quotes" not in results or not results["quotes"]:
            return f"❌ Nenhum ticker encontrado para '{company_name}'."

        for item in results["quotes"]:
            symbol = item.get("symbol", "")
            name = item.get("shortname", "") or item.get("longname", "")
            if symbol.endswith(".SA"):
                return f"✅ Ticker encontrado para {company_name}: {symbol} ({name})"

        first = results["quotes"][0]
        return f"⚠️ Ticker fora da B3 para {company_name}: {first['symbol']} ({first.get('shortname') or first.get('longname')})"

    except Exception as e:
        return f"Erro ao buscar ticker para '{company_name}': {str(e)}"