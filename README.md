# IDX Daily Screener

Dashboard analisis teknikal otomatis untuk saham LQ45 (Bursa Efek Indonesia).
Jalan sendiri tiap pagi jam 8 WIB (hari bursa), gratis 100%, tanpa server berbayar.

**Disclaimer:** Ini alat bantu riset, bukan rekomendasi finansial resmi.
Semua angka dihasilkan dari rumus teknikal otomatis. Selalu riset tambahan
dan kelola risiko sendiri.

---

## Cara Setup (sekali saja, ±15 menit)

### 1. Buat akun GitHub (kalau belum punya)
Daftar gratis di https://github.com/signup

### 2. Buat repository baru
- Klik tombol **"New"** / **"+"** → **New repository**
- Nama bebas, misal `idx-dashboard`
- Pilih **Public** (supaya GitHub Pages gratis bisa dipakai)
- Klik **Create repository**

### 3. Upload semua file dari folder ini
Cara termudah tanpa command line:
- Di halaman repo yang baru dibuat, klik **"uploading an existing file"**
- Drag & drop **seluruh isi folder ini** (jaga struktur foldernya: `scripts/`, `docs/`, `.github/workflows/`, `requirements.txt`)
- Klik **Commit changes**

> Kalau kamu familiar dengan git, bisa juga:
> ```bash
> git init
> git remote add origin https://github.com/USERNAME/idx-dashboard.git
> git add .
> git commit -m "Initial setup"
> git push -u origin main
> ```

### 4. Aktifkan GitHub Pages (untuk tampilkan dashboard)
- Buka repo → tab **Settings** → menu **Pages** (di sidebar kiri)
- Bagian **Source**, pilih branch `main` dan folder `/docs`
- Klik **Save**
- Tunggu 1-2 menit, GitHub akan kasih link seperti:
  `https://USERNAME.github.io/idx-dashboard/`
- **Ini link dashboard kamu — bookmark di HP!**

### 5. Jalankan analisis pertama kali secara manual
- Buka tab **Actions** di repo
- Klik workflow **"Daily IDX Screener"** di sidebar kiri
- Klik tombol **"Run workflow"** → **Run workflow** (hijau)
- Tunggu ±2-3 menit sampai selesai (tanda centang hijau)
- Refresh link dashboard kamu — data sudah muncul!

### 6. Selesai — otomatis jalan tiap hari
Mulai besok, workflow ini otomatis jalan sendiri tiap jam 8 pagi WIB
(hari Senin-Jumat). Kamu tinggal buka link dashboard kapan saja.

---

## Struktur File

```
idx-dashboard/
├── .github/workflows/daily.yml   # Jadwal otomatis (cron jam 8 pagi WIB)
├── scripts/analyze.py            # Logika ambil data + hitung indikator + sentimen
├── requirements.txt              # Library Python yang dibutuhkan
└── docs/
    ├── index.html                # Dashboard yang kamu lihat
    └── data.json                 # Hasil analisis (dibuat otomatis tiap hari)
```

## Fitur Tambahan (v4) — Alert Intraday Telegram

Sistem sekarang cek harga tiap 30 menit **selama jam bursa** (09:00-15:59 WIB,
Senin-Jumat) dan kirim notifikasi Telegram otomatis kalau:
- 🟢 Harga masuk **Buy Area**
- 🔴 Harga menyentuh **Stop Loss**
- 🎯 Harga mencapai **Target Profit 1**

Tiap kondisi cuma dikirim **sekali per hari per saham** (tidak spam berulang).

### Cara Setup Telegram Bot (±5 menit, gratis)

1. **Buat bot**: buka Telegram, cari **@BotFather**, kirim `/newbot`, ikuti
   instruksinya (kasih nama bebas). Nanti kamu dapat **token bot** seperti
   `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ` — simpan ini.

2. **Dapatkan Chat ID kamu**: cari **@userinfobot** di Telegram, klik Start,
   dia akan balas dengan Chat ID kamu (angka, misal `987654321`).

3. **Mulai chat dengan bot kamu sendiri**: cari nama bot yang kamu buat tadi
   di Telegram, klik **Start** (wajib, supaya bot bisa kirim pesan ke kamu).

4. **Masukkan ke GitHub Secrets** (supaya token tidak ketahuan publik):
   - Buka repo → **Settings** → **Secrets and variables** → **Actions**
   - Klik **New repository secret**, buat 2 secret:
     - Name: `TELEGRAM_BOT_TOKEN`, Value: token dari langkah 1
     - Name: `TELEGRAM_CHAT_ID`, Value: chat ID dari langkah 2

5. **Test manual**: tab **Actions** → workflow **"Intraday Alert"** → **Run
   workflow**. Kalau ada saham di watchlist yang masuk kondisi alert, kamu
   akan dapat pesan di Telegram dalam ±1 menit.

### Catatan

- Alert jalan otomatis mulai besok tanpa perlu setting apa-apa lagi.
- GitHub Actions jadwal cron tidak selalu presisi ke menit (kadang telat
  beberapa menit karena antrian server gratis) — cukup akurat untuk swing
  trading, tapi jangan andalkan untuk scalping detik-demi-detik.
- Watchlist yang dipantau = top picks dari hasil analisis pagi (`data.json`).
  Kalau mau pantau saham lain di luar itu, edit `docs/data.json` manual atau
  minta saya sesuaikan skripnya.

## Fitur Tambahan (v3)

- **Konfirmasi multi-timeframe** — sinyal daily sekarang dicocokkan dengan
  trend mingguan (dihitung dari resample data harian yang sudah ada, tanpa
  request tambahan). Kalau harian & mingguan **selaras uptrend** → confidence
  +15. Kalau **konflik** (harian kelihatan naik tapi mingguan masih downtrend
  besar) → confidence -15 dan ditandai badge "⚠ Konflik" di dashboard. Ini
  mengurangi jebakan classic: saham kelihatan bagus di chart harian padahal
  cuma technical rebound sesaat di tengah downtrend besar.

## Fitur Tambahan (v2)

- **Universe saham: IDX80** (bukan LQ45 lagi) — 80 saham periode 4 Mei-31 Juli
  2026. BEI evaluasi ulang tiap Januari/April/Juli/Oktober, jadi cek berkala
  apakah `IDX80_TICKERS` di `scripts/analyze.py` masih sesuai daftar terbaru.
- **Filter likuiditas** — karena IDX80 mencakup saham lebih kecil dari LQ45,
  sistem otomatis mengecek rata-rata nilai transaksi harian. Saham dengan
  nilai transaksi di bawah Rp 3 miliar/hari (bisa diubah di `min_value_idr`)
  kena penalti besar ke confidence score dan ditandai "⚠ Likuiditas Rendah"
  di dashboard, supaya kamu tidak terjebak saham yang susah dieksekusi.
- **Konteks pasar global** — Dow Jones, Nasdaq, Nikkei 225, Hang Seng, USD/IDR,
  Brent Crude, dan harga emas ditampilkan di bagian atas dashboard, karena arah
  IHSG di pagi hari sering dipengaruhi sentimen global semalam.
- **Volume signal (proxy foreign flow)** — rasio volume hari ini vs rata-rata
  20 hari, dilabeli "Accumulation" (volume tinggi + harga naik) atau
  "Distribution" (volume tinggi + harga turun). **Catatan jujur**: ini BUKAN
  data net buy/sell asing yang sesungguhnya (itu perlu data berbayar dari
  KSEI/broker seperti Stockbit Pro) — ini proxy gratis berbasis volume yang
  polanya sering mirip.
- **Position size calculator** — masukkan modal & risiko per transaksi (%),
  dashboard otomatis hitung berapa lot yang aman dibeli per saham berdasarkan
  jarak ke Stop Loss. Perhitungan ini di browser kamu sendiri, datanya tidak
  dikirim ke mana-mana.
- **Track record otomatis** — sistem menyimpan tiap rekomendasi ke
  `docs/history.json`, lalu di run berikutnya mengecek apakah harga sudah
  menyentuh TP1 (menang) atau SL (kalah) duluan. Win rate ditampilkan di
  dashboard supaya kamu bisa evaluasi akurasi sistem dari waktu ke waktu.

## Kustomisasi

- **Ubah daftar saham**: edit list `LQ45_TICKERS` di `scripts/analyze.py`
- **Ubah jam jalan**: edit baris `cron:` di `.github/workflows/daily.yml`
  (format: menit jam tanggal bulan hari — waktu dalam UTC, WIB = UTC+7)
- **Ubah tampilan dashboard**: edit `docs/index.html`

## Kalau Ingin Analisis Sentimen Lebih Pintar (opsional, berbayar kecil)

Saat ini sentimen dihitung dari kata kunci sederhana (gratis). Kalau nanti mau
upgrade ke analisis naratif oleh Claude (lebih tajam membaca konteks berita),
tinggal beri tahu saya — saya bisa tambahkan step pemanggilan Claude API di
`analyze.py` menggunakan API key kamu sendiri dari console.anthropic.com.
