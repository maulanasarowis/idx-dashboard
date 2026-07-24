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
# 1. DAFTAR SAHAM IDX80 (periode 4 Mei - 31 Juli 2026, evaluasi ulang oleh BEI
#    tiap Januari/April/Juli/Oktober - cek ulang & update tiap ada rebalancing)
# ---------------------------------------------------------------------------
IDX80_TICKERS = [
    "AADI", "ACES", "ADMR", "ADRO", "AKRA", "AMMN", "AMRT", "ANTM", "ARTO", "ASII",
    "BBCA", "BBNI", "BBRI", "BBTN", "BKSL", "BMRI", "BRMS", "BRPT", "BSDE", "BUKA",
    "BUMI", "CBDK", "CMRY", "CPIN", "CTRA", "CUAN", "DEWA", "DSNG", "ELSA", "EMTK",
    "ENRG", "ERAA", "ESSA", "EXCL", "GGRM", "GOTO", "HEAL", "HRTA", "HRUM", "ICBP",
    "INCO", "INDF", "INDY", "INKP", "INTP", "ISAT", "ITMG", "JPFA", "JSMR", "KIJA",
    "KLBF", "KPIG", "MAPA", "MAPI", "MBMA", "MDKA", "MEDC", "MIKA", "MYOR", "PANI",
    "PGAS", "PGEO", "PNLF", "PTBA", "PTRO", "PWON", "RAJA", "RATU", "SCMA", "SIDO",
    "SMGR", "SMRA", "SSIA", "TAPG", "TLKM", "TOWR", "TPIA", "UNTR", "UNVR", "WIFI",
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
HISTORY_PATH = "docs/history.json"
MAX_HISTORY_DAYS = 60

# Konteks pasar global - biasanya mempengaruhi arah IHSG di jam buka
GLOBAL_TICKERS = {
    "Dow Jones": "^DJI",
    "Nasdaq": "^IXIC",
    "Nikkei 225": "^N225",
    "Hang Seng": "^HSI",
    "USD/IDR": "IDR=X",
    "Brent Crude": "BZ=F",
    "Emas (Gold)": "GC=F",
}


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


def compute_liquidity(df: pd.DataFrame, lookback: int = 20, min_value_idr: float = 3_000_000_000):
    """
    Nilai transaksi harian rata-rata (Rp) = harga close x volume, dirata-ratakan
    N hari terakhir. Saham dengan nilai transaksi terlalu kecil rawan slippage
    besar (harga order kamu bisa jauh meleset dari harga yang terlihat di layar).
    Default ambang: Rp 3 miliar/hari - bisa diubah sesuai selera risiko kamu.
    """
    window = df.tail(lookback)
    avg_value = float((window["Close"] * window["Volume"]).mean())
    return {
        "avg_daily_value_idr": round(avg_value, 0),
        "is_liquid": avg_value >= min_value_idr,
    }


def support_resistance(df: pd.DataFrame, lookback: int = 20):
    window = df.tail(lookback)
    return float(window["Low"].min()), float(window["High"].max())


def compute_volume_signal(df: pd.DataFrame, avg_period: int = 20):
    """
    Proxy gratis untuk 'foreign flow' / bandarmology: rasio volume hari ini
    vs rata-rata volume 20 hari. Volume tidak wajar (>1.5x rata-rata) sering
    jadi sinyal awal ada pemain besar masuk/keluar - meski ini TIDAK sama
    persis dengan data net buy/sell asing yang sesungguhnya (itu perlu data
    berbayar dari KSEI/broker).
    """
    vol = df["Volume"]
    avg_vol = float(vol.rolling(avg_period).mean().iloc[-2]) if len(vol) > avg_period else float(vol.mean())
    today_vol = float(vol.iloc[-1])
    ratio = round(today_vol / avg_vol, 2) if avg_vol > 0 else 1.0

    # Arah harga saat volume naik -> indikasi accumulation vs distribution
    price_change = float(df["Close"].iloc[-1] - df["Close"].iloc[-2])
    if ratio >= 1.5 and price_change > 0:
        signal = "Accumulation (volume tinggi + harga naik)"
    elif ratio >= 1.5 and price_change < 0:
        signal = "Distribution (volume tinggi + harga turun)"
    elif ratio >= 1.5:
        signal = "Volume tidak wajar"
    else:
        signal = "Normal"

    return {"ratio": ratio, "signal": signal, "unusual": ratio >= 1.5}


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


def download_with_retry(symbol: str, period: str, interval: str, attempts: int = 3, delay: float = 2.0):
    """
    Yahoo Finance kadang rate-limit request dari server GitHub Actions,
    terutama setelah banyak request beruntun. Retry dengan jeda supaya
    lebih tahan terhadap gangguan sementara semacam itu.
    """
    last_error = None
    for i in range(attempts):
        try:
            df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df, None
            last_error = "data kosong"
        except Exception as e:
            last_error = str(e)
        time.sleep(delay)
    return pd.DataFrame(), last_error


def fetch_global_context():
    context = {}
    for name, symbol in GLOBAL_TICKERS.items():
        df, err = download_with_retry(symbol, period="5d", interval="1d", attempts=2, delay=1.5)
        if df.empty or len(df) < 2:
            continue
        try:
            last = float(df["Close"].iloc[-1])
            prev = float(df["Close"].iloc[-2])
            change_pct = round((last - prev) / prev * 100, 2)
            context[name] = {"last": round(last, 2), "change_pct": change_pct}
        except Exception:
            continue
    return context


def compute_weekly_trend(df: pd.DataFrame):
    """
    Konfirmasi multi-timeframe: resample data harian jadi mingguan (tanpa
    request tambahan ke Yahoo Finance), lalu cek trend & MACD di timeframe
    mingguan. Sinyal daily yang SEARAH dengan trend mingguan jauh lebih
    meyakinkan daripada sinyal daily doang - mengurangi jebakan "kelihatan
    bagus di chart harian tapi sebenarnya masih downtrend besar".
    """
    dfw = df.resample("W").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
    }).dropna()

    if len(dfw) < 10:
        return {"available": False}

    close_w = dfw["Close"]
    ma8_w = close_w.rolling(8).mean()
    macd_line_w, signal_line_w, _ = compute_macd(close_w)

    trend_up = bool(close_w.iloc[-1] > ma8_w.iloc[-1]) if not math.isnan(ma8_w.iloc[-1]) else None
    macd_bullish = bool(macd_line_w > signal_line_w)

    return {
        "available": True,
        "trend_up": trend_up,
        "macd_bullish": macd_bullish,
        "ma8": round(float(ma8_w.iloc[-1]), 0) if not math.isnan(ma8_w.iloc[-1]) else None,
    }


# ---------------------------------------------------------------------------
# TRACK RECORD - evaluasi rekomendasi kemarin, kena TP atau SL?
# ---------------------------------------------------------------------------
def evaluate_track_record(prev_picks, price_data):
    """
    Cek rekomendasi dari run sebelumnya: sejak tanggal rekomendasi dibuat,
    apakah harga sempat menyentuh salah satu TP (menang) atau SL (kalah)
    duluan? price_data adalah dict {ticker: df} hasil download run ini.
    """
    records = []
    for pick in prev_picks:
        ticker = pick["ticker"]
        df = price_data.get(ticker)
        if df is None:
            continue
        try:
            gen_date = datetime.fromisoformat(pick["_generated_at"]).date()
        except Exception:
            continue

        df_since = df[df.index.date > gen_date]
        if df_since.empty:
            continue  # belum ada candle baru sejak rekomendasi dibuat

        outcome = "Open"
        exit_price = None
        for _, row in df_since.iterrows():
            hit_sl = row["Low"] <= pick["stop_loss"]
            hit_tp1 = row["High"] >= pick["tp"][0]
            if hit_sl and hit_tp1:
                # ambigu dalam 1 candle, asumsikan konservatif: SL duluan
                outcome, exit_price = "SL Hit", pick["stop_loss"]
                break
            elif hit_sl:
                outcome, exit_price = "SL Hit", pick["stop_loss"]
                break
            elif hit_tp1:
                outcome, exit_price = "TP1 Hit", pick["tp"][0]
                break

        records.append({
            "ticker": ticker,
            "date": pick["_generated_at"][:10],
            "confidence": pick["confidence"],
            "buy_price": pick["last_price"],
            "outcome": outcome,
            "exit_price": exit_price,
        })
    return records


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
    volume_signal = compute_volume_signal(df)
    liquidity = compute_liquidity(df)
    weekly = compute_weekly_trend(df)

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

    # --- Konfirmasi multi-timeframe (harian vs mingguan) ---
    if weekly["available"] and weekly["trend_up"] is not None:
        if trend_up and weekly["trend_up"]:
            mtf_alignment = "Selaras (Uptrend Harian + Mingguan)"
            mtf_bonus = 15
        elif (not trend_up) and (not weekly["trend_up"]):
            mtf_alignment = "Selaras (Downtrend Harian + Mingguan)"
            mtf_bonus = 0
        elif trend_up and not weekly["trend_up"]:
            mtf_alignment = "Konflik (Naik harian, tapi mingguan masih downtrend)"
            mtf_bonus = -15
        else:
            mtf_alignment = "Konflik (Turun harian, tapi mingguan uptrend)"
            mtf_bonus = -5
    else:
        mtf_alignment = "Data mingguan belum cukup"
        mtf_bonus = 0

    # --- Confidence score sederhana (0-100), gabungan beberapa sinyal ---
    score = 50
    score += 15 if trend_up else -10
    score += 10 if macd_bullish else -10
    score += 10 if rsi_ok else -5
    score += 10 if near_support else 0
    score += 10 if sentiment["label"] == "Positif" else (-10 if sentiment["label"] == "Negatif" else 0)
    score += 8 if volume_signal["signal"].startswith("Accumulation") else (-8 if volume_signal["signal"].startswith("Distribution") else 0)
    score += 0 if liquidity["is_liquid"] else -25  # penalti besar untuk saham tipis/tidak likuid
    score += mtf_bonus
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
        "volume_signal": volume_signal,
        "liquidity": liquidity,
        "weekly_trend": weekly,
        "mtf_alignment": mtf_alignment,
        "_generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# 5. MAIN
# ---------------------------------------------------------------------------
def main():
    # --- Baca hasil run sebelumnya (untuk track record) ---
    prev_data = None
    try:
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            prev_data = json.load(f)
    except Exception:
        prev_data = None

    results = []
    errors = []
    price_data = {}

    # --- Ambil IHSG & konteks global DULUAN, sebelum request beruntun ke 80
    #     saham individual, supaya belum kena rate-limit Yahoo Finance ---
    ihsg_last, ihsg_change, ihsg_error = None, None, None
    ihsg_df, ihsg_err = download_with_retry("^JKSE", period="1mo", interval="1d")
    if not ihsg_df.empty and len(ihsg_df) >= 2:
        try:
            ihsg_last = float(ihsg_df["Close"].iloc[-1])
            ihsg_prev = float(ihsg_df["Close"].iloc[-2])
            ihsg_change = round((ihsg_last - ihsg_prev) / ihsg_prev * 100, 2)
        except Exception as e:
            ihsg_error = str(e)
    else:
        ihsg_error = ihsg_err or "gagal mengambil data IHSG"

    global_context = fetch_global_context()

    for ticker in IDX80_TICKERS:
        yf_symbol = f"{ticker}.JK"
        try:
            df = yf.download(yf_symbol, period="6mo", interval="1d", progress=False, auto_adjust=True)
            if df.empty or len(df) < 25:
                errors.append(ticker)
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            price_data[ticker] = df

            sentiment = fetch_news_sentiment(ticker, ticker)
            rec = build_recommendation(ticker, df, sentiment)
            results.append(rec)
            time.sleep(0.3)  # sopan ke server, hindari rate limit
        except Exception as e:
            errors.append(f"{ticker} ({e})")
            continue

    results.sort(key=lambda r: r["confidence"], reverse=True)

    # --- Track record: evaluasi rekomendasi run sebelumnya ---
    new_track_records = []
    if prev_data and prev_data.get("top_picks"):
        new_track_records = evaluate_track_record(prev_data["top_picks"], price_data)

    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            history_raw = json.load(f)
            history = history_raw.get("records", []) if isinstance(history_raw, dict) else history_raw
    except Exception:
        history = []

    # Update entri "Open" lama yang sekarang statusnya berubah, tambah entri baru
    existing_keys = {(h["ticker"], h["date"]) for h in history}
    for rec in new_track_records:
        key = (rec["ticker"], rec["date"])
        if key in existing_keys:
            history = [rec if (h["ticker"], h["date"]) == key else h for h in history]
        else:
            history.append(rec)

    history = history[-MAX_HISTORY_DAYS * 10:]  # batasi ukuran file

    closed = [h for h in history if h["outcome"] in ("TP1 Hit", "SL Hit")]
    wins = [h for h in closed if h["outcome"] == "TP1 Hit"]
    win_rate = round(len(wins) / len(closed) * 100, 1) if closed else None

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump({"records": history, "win_rate": win_rate, "total_closed": len(closed)}, f, ensure_ascii=False, indent=2)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ihsg": {"last": ihsg_last, "change_pct": ihsg_change, "error": ihsg_error},
        "global_context": global_context,
        "top_picks": results[:10],
        "all_results": results,
        "errors": errors,
        "track_record": {"win_rate": win_rate, "total_closed": len(closed)},
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Selesai. {len(results)} saham berhasil dianalisis, {len(errors)} gagal. Win rate: {win_rate}")


if __name__ == "__main__":
    main()
