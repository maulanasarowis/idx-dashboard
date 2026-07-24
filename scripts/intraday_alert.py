"""
IDX Intraday Alert - Kirim notifikasi Telegram saat harga saham watchlist
menyentuh Buy Area, Stop Loss, atau Target Profit 1.
============================================================================
Script ini jalan berkali-kali selama jam bursa (lihat .github/workflows/
intraday.yml), membaca watchlist dari docs/data.json (hasil analisis pagi),
cek harga terkini tiap saham, dan kirim pesan Telegram kalau ada kondisi
penting yang terpenuhi. Tiap kondisi cuma dikirim SEKALI per hari per saham
(disimpan di docs/alert_state.json) supaya tidak spam notifikasi berulang.
"""

import json
import os
import time
from datetime import datetime, timezone

import requests
import yfinance as yf

DATA_PATH = "docs/data.json"
STATE_PATH = "docs/alert_state.json"

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send_telegram(message: str):
    if not BOT_TOKEN or not CHAT_ID:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum diset di GitHub Secrets. Lewati pengiriman.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.status_code != 200:
            print("Gagal kirim Telegram:", resp.text)
    except Exception as e:
        print("Error kirim Telegram:", e)


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def get_latest_price(ticker: str):
    try:
        df = yf.download(f"{ticker}.JK", period="1d", interval="5m", progress=False, auto_adjust=True)
        if df.empty:
            return None
        if hasattr(df.columns, "get_level_values"):
            df.columns = df.columns.get_level_values(0)
        return float(df["Close"].iloc[-1])
    except Exception:
        return None


def main():
    data = load_json(DATA_PATH, {})
    picks = data.get("top_picks", [])
    if not picks:
        print("Watchlist kosong (docs/data.json belum ada top_picks). Jalankan analyze.py dulu.")
        return

    state = load_json(STATE_PATH, {})
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.get("date") != today:
        state = {"date": today, "alerted": {}}

    for pick in picks:
        ticker = pick["ticker"]
        price = get_latest_price(ticker)
        if price is None:
            continue

        alerted = state["alerted"].get(ticker, [])
        buy_low, buy_high = pick["buy_area"]
        sl = pick["stop_loss"]
        tp1 = pick["tp"][0]

        if buy_low <= price <= buy_high and "buy_zone" not in alerted:
            send_telegram(
                f"🟢 <b>{ticker}</b> masuk Buy Area\n"
                f"Harga sekarang: Rp {price:,.0f}\n"
                f"Buy Area: {buy_low:,.0f} - {buy_high:,.0f}\n"
                f"TP1: {tp1:,.0f} | SL: {sl:,.0f}"
            )
            alerted.append("buy_zone")

        if price <= sl and "sl_hit" not in alerted:
            send_telegram(
                f"🔴 <b>{ticker}</b> menyentuh Stop Loss\n"
                f"Harga sekarang: Rp {price:,.0f}\n"
                f"SL: {sl:,.0f}\n"
                f"Pertimbangkan cut loss sesuai rencana risk management kamu."
            )
            alerted.append("sl_hit")

        if price >= tp1 and "tp1_hit" not in alerted:
            send_telegram(
                f"🎯 <b>{ticker}</b> mencapai Target Profit 1\n"
                f"Harga sekarang: Rp {price:,.0f}\n"
                f"TP1: {tp1:,.0f}"
            )
            alerted.append("tp1_hit")

        state["alerted"][ticker] = alerted
        time.sleep(0.3)

    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print("Selesai cek alert intraday.")


if __name__ == "__main__":
    main()
