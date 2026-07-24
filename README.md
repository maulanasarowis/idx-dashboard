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
