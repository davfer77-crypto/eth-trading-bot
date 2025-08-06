import os
import certifi
os.environ['SSL_CERT_FILE'] = certifi.where()

import pandas as pd
import requests
import time
from datetime import datetime
import pytz
import yfinance as yf

from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

# === CONFIGURACIÓN DE TELEGRAM ===
TELEGRAM_TOKEN = '8261518854:AAF8osWz7Jln1O_z2RD2srrpAl3mAjjUI1o'
TELEGRAM_CHAT_ID = '6388740211'

def obtener_rsi(close, window=14):
    return RSIIndicator(close=close, window=window).rsi().iloc[-1]

def obtener_macd(close):
    macd = MACD(close=close)
    return macd.macd().iloc[-1], macd.macd_signal().iloc[-1]

def obtener_ema(close, window):
    return EMAIndicator(close=close, window=window).ema_indicator().iloc[-1]

def obtener_atr(high, low, close):
    return AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range().iloc[-1]

def detectar_ruptura(df):
    vela_actual = df.iloc[-1]
    vela_anterior = df.iloc[-2]
    cambio = abs(vela_actual['Close'] - vela_anterior['Close']) / vela_anterior['Close']
    volumen_sube = vela_actual['Volume'] > df['Volume'].rolling(window=10).mean().iloc[-1]
    return cambio > 0.01 and volumen_sube

def analizar_mercado():
    ahora = datetime.now(pytz.timezone('America/New_York'))
    mercado_abierto = ahora.weekday() < 5 and 9 <= ahora.hour < 16

    df_eth = yf.download('ETH-USD', interval='5m', period='2d')
    df_btc = yf.download('BTC-USD', interval='5m', period='2d')
    rsi_sp500 = None
    if mercado_abierto:
        df_sp = yf.download('^GSPC', interval='5m', period='1d')
        rsi_sp500 = obtener_rsi(df_sp['Close'])

    rsi_eth = obtener_rsi(df_eth['Close'])
    rsi_btc = obtener_rsi(df_btc['Close'])
    macd, signal = obtener_macd(df_eth['Close'])
    ema_50 = obtener_ema(df_eth['Close'], 50)
    ema_200 = obtener_ema(df_eth['Close'], 200)
    precio_actual = df_eth['Close'].iloc[-1]
    atr = obtener_atr(df_eth['High'], df_eth['Low'], df_eth['Close'])

    condiciones_long = [
        rsi_eth < 30,
        macd > signal,
        ema_50 > ema_200,
        rsi_btc < 35,
        (rsi_sp500 and rsi_sp500 < 40) if rsi_sp500 else True
    ]
    prob_long = sum(condiciones_long) / len(condiciones_long)

    condiciones_short = [
        rsi_eth > 70,
        macd < signal,
        ema_50 < ema_200,
        rsi_btc > 65,
        (rsi_sp500 and rsi_sp500 > 60) if rsi_sp500 else True
    ]
    prob_short = sum(condiciones_short) / len(condiciones_short)

    mejor_opcion = "LONG" if prob_long > prob_short else "SHORT" if prob_short > prob_long else "NEUTRAL"

    ruptura = detectar_ruptura(df_eth)
    señal = mejor_opcion if max(prob_long, prob_short) > 0.6 else None

    if señal == 'LONG':
        entry = precio_actual
        tp = entry + atr * 2
        sl = entry - atr * 1.5
    elif señal == 'SHORT':
        entry = precio_actual
        tp = entry - atr * 2
        sl = entry + atr * 1.5
    else:
        entry = tp = sl = None

    mensaje = f'''
Análisis técnico ETH/USDT - cada 15 min
Hora (NY): {ahora.strftime('%Y-%m-%d %H:%M:%S')}

Precio actual: {round(precio_actual, 2)}
RSI ETH: {round(rsi_eth, 2)} | RSI BTC: {round(rsi_btc, 2)} | RSI S&P500: {round(rsi_sp500, 2) if rsi_sp500 else 'Cerrado'}
MACD: {round(macd, 2)} | Signal: {round(signal, 2)}
EMA50: {round(ema_50, 2)} | EMA200: {round(ema_200, 2)}

Probabilidad de éxito:
- LONG: {round(prob_long * 100)}%
- SHORT: {round(prob_short * 100)}%
Mejor opción: {mejor_opcion}

Señal activa: {señal or 'Sin señal'}
Entrada: {round(entry, 2) if entry else 'N/A'}
TP: {round(tp, 2) if tp else 'N/A'}
SL: {round(sl, 2) if sl else 'N/A'}

Ruptura detectada: {'SÍ' if ruptura else 'No'}
'''

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}
    )
    print("Mensaje enviado")

while True:
    print("Ejecutando análisis ETH/USDT...")
    try:
        analizar_mercado()
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(900)  # 15 minutos
