from typing import Dict
from datetime import datetime
import yfinance as yf
import pandas as pd
from ta.trend import MACD, SMAIndicator, EMAIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands
from ta.volume import OnBalanceVolumeIndicator, AccDistIndexIndicator

# ===== FUNÇÕES AUXILIARES DE INTERPRETAÇÃO =====

def calculate_slope(series: pd.Series, window: int = 5) -> float:
    return series.diff().tail(window).mean()

def interpret_rsi(rsi: float) -> str:
    if rsi > 70:
        return "⚠️ RSI indica sobrecompra"
    elif rsi < 30:
        return "⚠️ RSI indica sobrevenda"
    return "RSI em zona neutra"

def interpret_macd(macd_line: float, macd_signal: float, macd_diff: float) -> str:
    if macd_diff > 0 and macd_line > macd_signal:
        return "↗️ MACD sugere tendência de alta"
    elif macd_diff < 0 and macd_line < macd_signal:
        return "↘️ MACD sugere tendência de baixa"
    return "MACD em zona neutra"

def interpret_stochastic(k: float, d: float) -> str:
    if k > 80 and d > 80:
        return "⚠️ Estocástico em região de sobrecompra"
    elif k < 20 and d < 20:
        return "⚠️ Estocástico em região de sobrevenda"
    return "Estocástico em zona neutra"

def interpret_sma_slopes(slopes: Dict[str, float]) -> str:
    if slopes.get("SMA_20", 0) > 0 and slopes.get("SMA_50", 0) > 0:
        return "↗️ Médias móveis curtas com inclinação positiva"
    elif slopes.get("SMA_20", 0) < 0 and slopes.get("SMA_50", 0) < 0:
        return "↘️ Médias móveis curtas com inclinação negativa"
    return "Inclinação neutra nas médias móveis"

def format_price_vs_sma(current: float, sma: float) -> str:
    pct = (current / sma - 1) * 100
    return f"{pct:.1f}%"

# ===== FUNÇÃO PRINCIPAL DE INDICADORES =====

def get_technical_indicators(stock_data: pd.DataFrame) -> Dict[str, float]:
    if stock_data.empty:
        return {}

    close = stock_data['Close']
    high = stock_data['High']
    low = stock_data['Low']
    volume = stock_data['Volume']

    indicators = {}

    # RSI
    indicators['RSI_14'] = RSIIndicator(close, window=14).rsi().iloc[-1]

    # MACD
    macd = MACD(close)
    indicators['MACD_12_26_line'] = macd.macd().iloc[-1]
    indicators['MACD_12_26_signal'] = macd.macd_signal().iloc[-1]
    indicators['MACD_12_26_diff'] = macd.macd_diff().iloc[-1]

    # Bollinger Bands
    bb = BollingerBands(close)
    indicators['BB_20_2_superior'] = bb.bollinger_hband().iloc[-1]
    indicators['BB_20_2_inferior'] = bb.bollinger_lband().iloc[-1]
    indicators['BB_20_2_medio'] = bb.bollinger_mavg().iloc[-1]

    # Médias móveis + slope
    for window in [20, 50, 200]:
        sma_series = SMAIndicator(close, window=window).sma_indicator()
        indicators[f'SMA_{window}'] = sma_series.iloc[-1]
        indicators[f'SMA_{window}_slope'] = calculate_slope(sma_series)

    # Estocástico
    stoch = StochasticOscillator(high, low, close)
    indicators['Stoch_K'] = stoch.stoch().iloc[-1]
    indicators['Stoch_D'] = stoch.stoch_signal().iloc[-1]

    return indicators

# ===== FUNÇÃO DE ANÁLISE PRINCIPAL =====

def get_company_indicators(ticker: str) -> str:
    try:
        stock = yf.Ticker(ticker)
        result_lines = [f"📊 Análise de Investimento - {ticker.upper()} ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n"]

        info = stock.info
        if not info:
            return "❌ Dados não encontrados."

        current_price = info.get('currentPrice')
        volume = info.get('volume')
        avg_volume = info.get('averageVolume')
        avg_volume_10d = info.get('averageVolume10days')

        result_lines.append("=== Preço e Volume ===")
        if current_price: result_lines.append(f"Preço Atual: R$ {current_price:,.2f}")
        if volume: result_lines.append(f"Volume Atual: {volume:,}")
        if avg_volume:
            result_lines.append(f"Volume Médio: {avg_volume:,}")
            result_lines.append(f"Volume vs Média: {(volume / avg_volume) * 100:.1f}%")
        if avg_volume_10d: result_lines.append(f"Volume Médio (10d): {avg_volume_10d:,}")

        hist = stock.history(period="200d")
        if hist.empty:
            result_lines.append("Dados históricos insuficientes.")
            return "\n".join(result_lines)

        indicators = get_technical_indicators(hist)
        current = hist['Close'].iloc[-1]


        decision = score_signal(indicators)
        result_lines.append(f"\n🎯 Recomendação: {decision['signal'].upper()} (score: {decision['score']})")
        result_lines.append("Motivos:")
        for motivo in decision["justificativas"]:
            result_lines.append(f"- {motivo}")

        
        

        result_lines.append("\n=== Análise Técnica ===")
        result_lines.append(f"RSI (14): {indicators['RSI_14']:.2f} - {interpret_rsi(indicators['RSI_14'])}")
        result_lines.append(f"MACD: {indicators['MACD_12_26_line']:.2f}, Sinal: {indicators['MACD_12_26_signal']:.2f}, Hist: {indicators['MACD_12_26_diff']:.2f}")
        result_lines.append(interpret_macd(indicators['MACD_12_26_line'], indicators['MACD_12_26_signal'], indicators['MACD_12_26_diff']))
        result_lines.append(f"Estocástico %K: {indicators['Stoch_K']:.2f}, %D: {indicators['Stoch_D']:.2f}")
        result_lines.append(interpret_stochastic(indicators['Stoch_K'], indicators['Stoch_D']))

        result_lines.append("\nMédias Móveis:")
        for w in [20, 50, 200]:
            result_lines.append(f"Preço vs MM{w}: {format_price_vs_sma(current, indicators[f'SMA_{w}'])}")
        result_lines.append(interpret_sma_slopes({k: indicators[k] for k in indicators if 'slope' in k}))
        if indicators['SMA_50'] > indicators['SMA_200']:
            result_lines.append("✨ Golden Cross (MM50 > MM200)")
        elif indicators['SMA_50'] < indicators['SMA_200']:
            result_lines.append("💀 Death Cross (MM50 < MM200)")

        result_lines.append("\nBandas de Bollinger:")
        result_lines.append(f"Superior: {indicators['BB_20_2_superior']:.2f}, Média: {indicators['BB_20_2_medio']:.2f}, Inferior: {indicators['BB_20_2_inferior']:.2f}")
        if current > indicators['BB_20_2_superior']:
            result_lines.append("⚠️ Preço acima da banda superior")
        elif current < indicators['BB_20_2_inferior']:
            result_lines.append("⚠️ Preço abaixo da banda inferior")

        # Fundamentais
        result_lines.append("\n=== Fundamentais ===")
        if info.get('trailingPE'): result_lines.append(f"P/L: {info['trailingPE']:.2f}")
        if info.get('priceToBook'): result_lines.append(f"P/VP: {info['priceToBook']:.2f}")
        if info.get('enterpriseToEbitda'): result_lines.append(f"EV/EBITDA: {info['enterpriseToEbitda']:.2f}")

        result_lines.append("\nRentabilidade:")
        if info.get('returnOnEquity'): result_lines.append(f"ROE: {info['returnOnEquity'] * 100:.2f}%")
        if info.get('ebitdaMargins'): result_lines.append(f"Margem EBITDA: {info['ebitdaMargins'] * 100:.2f}%")
        if info.get('profitMargins'): result_lines.append(f"Margem Líquida: {info['profitMargins'] * 100:.2f}%")

        result_lines.append("\nDividendos:")
        dy = info.get('dividendYield')
        div_rate = info.get('dividendRate')
        if div_rate and current_price:
            dy_calc = (div_rate / current_price) #* 100
            result_lines.append(f"Dividend Yield (calculado): {dy_calc:.2f}%")
        elif dy:
            # result_lines.append(f"Dividend Yield (raw): {dy * 100:.2f}%")
            result_lines.append(f"Dividend Yield (raw): {dy:.2f}%")

        return "\n".join(result_lines)

    except Exception as e:
        print(f"Erro ao buscar indicadores para {ticker}: {str(e)}")
        return f"Erro ao buscar indicadores para {ticker}: {str(e)}"
    


def score_signal(indicators: Dict[str, float]) -> Dict[str, str]:
    """
    Gera uma recomendação com base em regras simples a partir dos indicadores técnicos.
    
    Retorna:
        - score (int): pontuação total baseada nos sinais
        - signal (str): 'comprar', 'manter' ou 'vender'
        - rationale (List[str]): justificativas
    """
    score = 0
    rationale = []

    # RSI
    rsi = indicators.get("RSI_14", 50)
    if rsi < 30:
        score += 1
        rationale.append("RSI indica sobrevenda")
    elif rsi > 70:
        score -= 1
        rationale.append("RSI indica sobrecompra")

    # MACD
    macd_line = indicators.get("MACD_12_26_line", 0)
    macd_signal = indicators.get("MACD_12_26_signal", 0)
    macd_diff = indicators.get("MACD_12_26_diff", 0)
    if macd_diff > 0 and macd_line > macd_signal:
        score += 1
        rationale.append("MACD com viés de alta")
    elif macd_diff < 0 and macd_line < macd_signal:
        score -= 1
        rationale.append("MACD com viés de baixa")

    # Estocástico
    stoch_k = indicators.get("Stoch_K", 50)
    stoch_d = indicators.get("Stoch_D", 50)
    if stoch_k < 20 and stoch_d < 20:
        score += 1
        rationale.append("Estocástico em sobrevenda")
    elif stoch_k > 80 and stoch_d > 80:
        score -= 1
        rationale.append("Estocástico em sobrecompra")

    # Médias móveis
    price_vs_sma20 = indicators.get("SMA_20_slope", 0)
    price_vs_sma50 = indicators.get("SMA_50_slope", 0)
    if price_vs_sma20 > 0 and price_vs_sma50 > 0:
        score += 1
        rationale.append("Médias móveis com inclinação positiva")
    elif price_vs_sma20 < 0 and price_vs_sma50 < 0:
        score -= 1
        rationale.append("Médias móveis com inclinação negativa")

    # Definir sinal final
    if score >= 2:
        signal = "comprar"
    elif score <= -2:
        signal = "vender"
    else:
        signal = "manter"

    return {
        "score": score,
        "signal": signal,
        "justificativas": rationale
    }