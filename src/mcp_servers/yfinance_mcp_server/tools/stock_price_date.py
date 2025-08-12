import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

TZ = "America/Sao_Paulo"

def _hist_with_local_tz(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Baixa histórico e normaliza o índice para o fuso de São Paulo."""
    hist = yf.Ticker(ticker).history(start=start, end=end, interval="1d")
    if hist.empty:
        return hist

    idx = hist.index
    if idx.tz is None:          # índice “naive”
        idx = idx.tz_localize("UTC")
    hist.index = idx.tz_convert(TZ).normalize()
    return hist


def get_stock_price_on_date(ticker: str, date: str) -> str:
    """Retorna o preço da ação em uma data específica.
    parameters:
        ticker: ticker of the stock (ex: PETR4.SA)
        target_date: data da consulta no formato (YYYY-MM-DD)
    """
    print(f"Buscando preço de {ticker} em {date}...")
    try:
        # ── valida formato da data ──────────────────────────────────
        try:
            target = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            return "A data deve estar no formato AAAA-MM-DD."

        # Baixa ~15 dias para trás para cobrir feriados prolongados
        start_window = (target - timedelta(days=15)).strftime("%Y-%m-%d")
        end_window   = (target + timedelta(days=1)).strftime("%Y-%m-%d")

        hist = _hist_with_local_tz(ticker, start=start_window, end=end_window)

        if hist.empty or "Close" not in hist.columns:
            return f"Nenhum dado encontrado para o ticker {ticker}."

        # Seleciona o último preço ≤ target_date
        prices = hist["Close"].dropna()
        prices = prices[prices.index.date <= target]

        if prices.empty:
            return f"Sem preço disponível para {ticker} até {date}."

        price_date = prices.index[-1].strftime("%Y-%m-%d")
        price      = prices.iloc[-1]

        retorno = (
            f"O preço de {ticker.upper()} em {price_date} foi "
            f"R$ {price:.2f}"
        )
        if price_date != date:
            retorno += " (último pregão anterior à data solicitada)."
        return retorno

    except Exception as e:
        return f"Erro ao buscar dados de {ticker}: {e}"
