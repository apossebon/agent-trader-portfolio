import yfinance as yf

def get_stock_price(ticker: str, period: str = "2d", interval: str = "1d") -> str:
    print(f"Buscando preço de {ticker} com período {period} e intervalo {interval}")
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period, interval=interval)

        if hist.empty or "Close" not in hist.columns:
            return f"Nenhum dado encontrado para o ticker {ticker}."

        price_series = hist["Close"].dropna()
        if price_series.empty:
            return f"Preço de fechamento indisponível para {ticker}."

        price = price_series.iloc[-1]
        return f"O preço mais recente de {ticker.upper()} é R$ {price:.2f}"
    except Exception as e:
        return f"Erro ao buscar dados de {ticker}: {str(e)}"