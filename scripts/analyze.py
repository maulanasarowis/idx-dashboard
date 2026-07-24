"""
IDX Daily Screener - Analisis Teknikal Otomatis Saham LQ45
============================================================
Script ini:
1. Mengambil data harga historis saham LQ45 dari Yahoo Finance (yfinance)
2. Menghitung indikator teknikal (RSI, MACD, MA20/MA50, Support/Resistance, ATR)
3. Menentukan Buy Area, TP1/TP2/TP3, Stop Loss, Risk-Reward Ratio, Confidence Score
4. Mengambil headline berita tiap saham (Google News RSS) dan menghitung skor sentimen
   sederhana berbasis kata kunci (gratis, tanpa API berbayar)
5. Menyimpan semua hasil ke docs/data.json untuk ditampilkan di dashboard (index.html)

Catatan penting:
- Ini BUKAN rekomendasi finansial resmi. Semua angka dihasilkan dari rumus teknikal
  sederhana, bukan analisis manusia berlisensi. Gunakan sebagai alat bantu riset saja.
- Data yfinance untuk IDX biasanya delay ringan, bukan real-time murni.
"""

import json
import time
import math
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# 1. DAFTAR SAHAM LQ45 (edit bebas sesuai kebutuhan - update berkala oleh IDX)
# ---------------------------------------------------------------------------
LQ45_TICKERS = [
    "ACES", "ADRO", "AKRA", "AMMN", "AMRT", "ANTM", "ARTO", "ASII", "AUTO", "AVIA",
    "BBCA", "BBNI", "BBRI", "BBTN", "BBYB", "BFIN", "BMRI", "BMTR", "BRIS", "BRPT",
    "BUKA", "CPIN", "CTRA", "ESSA", "EXCL", "GGRM", "GOTO", "HRUM", "ICBP", "INCO",
    "INDF", "INKP", "INTP", "ISAT", "ITMG", "JPFA", "JSMR", "KLBF", "MAPI", "MBMA",
    "MDKA", "MEDC", "MIKA", "PGAS", "PGEO", "PTBA", "SIDO", "SMGR", "SRTG", "TLKM",
    "TOWR", "UNTR", "UNVR",
]

NEWS_KEYWORDS_POS = [
    "naik", "menguat", "laba", "untung", "tumbuh", "ekspansi", "akuisisi",
    "kinerja positif", "rekor", "melonjak", "dividen", "buyback", "kontrak baru",
    "penjualan meningkat", "target tercapai", "optimis", "prospek cerah",
]
NEWS_KEYWORDS_NEG = [
    "turun", "melemah", "rugi", "anjlok", "penurunan", "gagal", "sanksi",
    "kasus hukum", "denda", "phk", "restrukturisasi utang", "gugatan",
    "kinerja negatif", "delisting", "suspensi", "koreksi tajam", "kekhawatiran",
]

OUTPUT_PATH = "docs/data.json"


# ---------------------------------------------------------------------------
# 2. INDIKATOR TEKNIKAL
# ---------------------------------------------------------------------------
def compute_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not math.isnan(rsi.iloc[-1]) else 50.0


def compute_macd(close: pd.Series):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(hist.iloc[-1])


def compute_atr(df: pd.DataFrame, period: int = 14) -> float:
    high, low, close = df["High"], df["Low"], df["Close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])


def support_resistance(df: pd.DataFrame, lookback: int = 20):
    window = df.tail(lookback)
    return float(window["Low"].min()), float(window["High"].max())


# ---------------------------------------------------------------------------
# 3. SENTIMEN BERITA (GRATIS, VIA GOOGLE NEWS RSS + KEYWORD SCORING)
# ---------------------------------------------------------------------------
def fetch_news_sentiment(ticker: str, company_query: str):
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(company_query + ' saham')}&hl=id&gl=ID&ceid=ID:id"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        titles = [item.find("title").text or "" for item in root.findall(".//item")][:8]
    except Exception:
        titles = []

    pos, neg = 0, 0
    for t in titles:
        low = t.lower()
        pos += sum(1 for k in NEWS_KEYWORDS_POS if k in low)
        neg += sum(1 for k in NEWS_KEYWORDS_NEG if k in low)

    if pos + neg == 0:
        label = "Netral"
        score = 0
    else:
        score = round((pos - neg) / (pos + neg), 2)
        label = "Positif" if score > 0.15 else "Negatif" if score < -0.15 else "Netral"

    return {"label": label, "score": score, "headlines": titles[:5]}


# ---------------------------------------------------------------------------
# 4. LOGIKA REKOMENDASI (Buy Area, TP1-3, SL, RRR, Confidence)
# ---------------------------------------------------------------------------
def build_recommendation(ticker: str, df: pd.DataFrame, sentiment: dict):
    close = df["Close"]
    last_price = float(close.iloc[-1])
    ma20 = float(close.rolling(20).mean().iloc[-1])
    ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else ma20
    rsi = compute_rsi(close)
    macd_line, signal_line, hist = compute_macd(close)
    atr = compute_atr(df)
    support, resistance = support_resistance(df)

    trend_up = last_price > ma20 > ma50
    macd_bullish = macd_line > signal_line
    rsi_ok = 35 <= rsi <= 65  # zona sehat, belum overbought/oversold ekstrem
    near_support = (last_price - support) / max(support, 1) < 0.05

    # --- Buy area: sekitar support / MA20, mana yang lebih relevan ---
    buy_low = round(min(support, ma20) * 0.995, 0)
    buy_high = round(max(support, ma20) * 1.01, 0)

    # --- Stop loss: di bawah support terakhir minus buffer ATR ---
    stop_loss = round(support - atr * 0.5, 0)
    risk = max(last_price - stop_loss, 1)

    tp1 = round(last_price + risk * 1.5, 0)
    tp2 = round(last_price + risk * 2.5, 0)
    tp3 = round(max(resistance, last_price + risk * 4), 0)

    rrr = round((tp1 - last_price) / risk, 2) if risk > 0 else 0

    # --- Confidence score sederhana (0-100), gabungan beberapa sinyal ---
    score = 50
    score += 15 if trend_up else -10
    score += 10 if macd_bullish else -10
    score += 10 if rsi_ok else -5
    score += 10 if near_support else 0
    score += 10 if sentiment["label"] == "Positif" else (-10 if sentiment["label"] == "Negatif" else 0)
    confidence = int(max(0, min(100, score)))

    return {
        "ticker": ticker,
        "last_price": last_price,
        "rsi": round(rsi, 1),
        "macd_hist": round(hist, 2),
        "ma20": round(ma20, 0),
        "ma50": round(ma50, 0),
        "support": round(support, 0),
        "resistance": round(resistance, 0),
        "buy_area": [buy_low, buy_high],
        "tp": [tp1, tp2, tp3],
        "stop_loss": stop_loss,
        "rrr": rrr,
        "confidence": confidence,
        "trend_up": trend_up,
        "sentiment": sentiment,
    }


# ---------------------------------------------------------------------------
# 5. MAIN
# ---------------------------------------------------------------------------
def main():
    results = []
    errors = []

    for ticker in LQ45_TICKERS:
        yf_symbol = f"{ticker}.JK"
        try:
            df = yf.download(yf_symbol, period="6mo", interval="1d", progress=False, auto_adjust=True)
            if df.empty or len(df) < 25:
                errors.append(ticker)
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            sentiment = fetch_news_sentiment(ticker, ticker)
            rec = build_recommendation(ticker, df, sentiment)
            results.append(rec)
            time.sleep(0.3)  # sopan ke server, hindari rate limit
        except Exception as e:
            errors.append(f"{ticker} ({e})")
            continue

    results.sort(key=lambda r: r["confidence"], reverse=True)

    # Ringkasan pasar sederhana dari IHSG
    try:
        ihsg = yf.download("^JKSE", period="1mo", interval="1d", progress=False, auto_adjust=True)
        ihsg_last = float(ihsg["Close"].iloc[-1])
        ihsg_prev = float(ihsg["Close"].iloc[-2])
        ihsg_change = round((ihsg_last - ihsg_prev) / ihsg_prev * 100, 2)
    except Exception:
        ihsg_last, ihsg_change = None, None

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ihsg": {"last": ihsg_last, "change_pct": ihsg_change},
        "top_picks": results[:10],
        "all_results": results,
        "errors": errors,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Selesai. {len(results)} saham berhasil dianalisis, {len(errors)} gagal.")


if __name__ == "__main__":
    main()
