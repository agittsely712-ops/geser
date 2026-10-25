# GESER: Gravity-tilt Estimation for Sedentary Event Reminders

**Kepanjangan:** **G**ravity-tilt **E**stimation for **S**edentary **E**vent **R**eminders
**Arti kata:** *Geser* berarti berpindah sedikit dari posisi semula.
**Tagline:** *"Geser dikit, yuk."*

> **Penafian Penting (Disclaimer):**
> Sistem ini hanya **MEMPERKIRAKAN** durasi diam dan perubahan kemiringan dari gerakan perangkat, **bukan** mengukur postur tubuh dan **bukan** alat medis.

---

## 1. Tujuan dan Cara Kerja Singkat

Mahasiswa sering duduk di posisi yang sama terlalu lama saat mengerjakan tugas tanpa menyadari posisinya hampir tidak berubah. **GESER** memantau kemiringan dan gerakan menggunakan dua HP Android yang terhubung ke broker MQTT Cloud (HiveMQ TLS), lalu memberikan pengingat bertahap serta membatalkannya otomatis (*auto-clear*) ketika pengguna benar-benar berganti posisi.

```text
+---------------------------+        MQTT over TLS (8883)        +---------------------------+
| HP A: body (Saku Dada)    | -- edge/body/telemetry (QoS 1) --> |                           |
| Sensor: Accel + Gyro      | <- reminders (Getar L2 & L3) ----- |   Broker HiveMQ Publik    |
+---------------------------+                                    |   broker.hivemq.com:8883  |
                                                                 |                           |
+---------------------------+                                    |                           |
| HP B: desk (Di Atas Meja) | -- edge/desk/telemetry (QoS 1) --> |                           |
| Sensor: Accel + Gyro      | <- reminders (Notifikasi L1-L3) -- |                           |
+---------------------------+                                    +-------------+-------------+
                                                                               |
                                                                               v
+---------------------------+        Satu Jaringan Lokal         +---------------------------+
| Dashboard Streamlit       | <--- session, events, control ---> | Session Engine (Laptop)   |
| (Kontrol & Grafik Live)   |                                    | Processing 2 & State Mach |
+---------------------------+                                    +---------------------------+
```

- **`body` (HP A di saku baju dada):** Mewakili gerakan dan kemiringan tubuh, sekaligus menjadi aktuator getar (`termux-vibrate`).
- **`desk` (HP B di atas meja):** Menjadi referensi penolak gangguan (saat meja diguncang/digebrak, gerakan tidak dihitung sebagai perpindahan posisi tubuh) dan penampil notifikasi (`termux-notification`).

---

## 2. Jalan dalam 10 Menit (Panduan Langkah demi Langkah)

### Langkah 1: Persiapan di Laptop (Windows PowerShell / Linux / macOS)

Pastikan Python 3.10+ sudah terpasang. Buka terminal di folder utama `geser/`:

```powershell
# 1. Buat dan aktifkan virtual environment
python -m venv .venv
# Di Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Di Linux/macOS/Termux:
# source .venv/bin/activate

# 2. Pasang paket geser beserta dependensi dashboard dan pengujian
pip install -e ".[dashboard,dev]"

# 3. Salin file konfigurasi .env
cp .env.example .env
```

### Langkah 2: Buat dan Isi `PROJECT_ID` Unik di `.env`

Program **menolak berjalan** bila `PROJECT_ID` masih bernilai placeholder `geser-kelompok-GANTI`.
1. Jalankan perintah berikut untuk mencetak saran nilai unik dengan sufiks acak 4 karakter:
   ```powershell
   python tools/suggest_project_id.py
   ```
2. Buka berkas `.env` dan ganti baris `PROJECT_ID=...` dengan hasil perintah tadi (contoh: `PROJECT_ID=geser-kelompok-9k2a`).
3. **Wajib:** Gunakan `PROJECT_ID` yang **sama persis** di Laptop, HP `body`, dan HP `desk`.

---

## 3. Tiga Perintah Inti Menjalankan Sistem

Buka **3 terminal berbeda** di laptop (atau 2 terminal di laptop + 2 Termux di HP Android):

### Perintah 1: Jalankan Session Engine (di Laptop)
```powershell
geser-engine
```
*(Untuk demo cepat tanpa menunggu 30 menit nyata, Anda bisa langsung menyertakan skala waktu: `geser-engine --time-scale 30`)*

### Perintah 2: Jalankan Kedua Edge (`body` dan `desk`)

**Cara A - Menggunakan 2 HP Android Fisik (Termux):**
Lihat panduan instalasi Termux di `docs/SETUP.md`, lalu jalankan:
```bash
# Di HP A (masukkan ke saku baju dada):
geser-edge --role body

# Di HP B (letakkan di atas meja):
geser-edge --role desk
```

**Cara B - Menggunakan Mode Simulasi di Laptop (untuk mencoba tanpa HP):**
```powershell
# Terminal Edge 1 (body):
geser-edge --role body --simulate still

# Terminal Edge 2 (desk):
geser-edge --role desk --simulate still
```
*(Profil simulasi yang tersedia: `still`, `fidget`, `shake`)*

### Perintah 3: Jalankan Dashboard Streamlit (di Laptop)
```powershell
streamlit run src/geser/dashboard/app.py
```
Buka alamat lokal yang muncul di terminal (biasanya `http://localhost:8501`) pada peramban.

---

## 4. Cara Mengoperasikan Sesi & Fitur Demo (`TIME_SCALE`)

1. Pada halaman **Live** di Dashboard, pastikan indikator **HP Body** dan **HP Desk** berstatus **ONLINE**.
2. Geser slider **Skala Waktu Demo (`TIME_SCALE`)** ke **`30`** lalu klik **Terapkan Skala Waktu** (dengan skala 30x, ambang 30 menit dicapai dalam **1 menit nyata**).
3. Klik tombol **Start** untuk memulai sesi (status masuk ke `SETTLING` untuk mengukur noise floor adaptif).
4. Duduk tegak normal, lalu klik tombol **Kalibrasi 5 dtk** untuk menyimpan posisi acuan (`baseline`).
5. Diamkan HP `body` untuk mengamati kenaikan durasi diam hingga memicu pengingat **Level 1** (`STILL_LONG`), **Level 2** (`STILL_VERY_LONG`), dan **Level 3** (`STILL_CRITICAL`).
6. Miringkan badan/HP `body` (>= 15 derajat) tanpa mengguncang meja untuk melihat pengingat dibatalkan otomatis (**Auto-Clear**) dan skor bertambah.

---

## 5. Alat Bantu Tambahan (`tools/`) & Dokumen Lengkap (`docs/`)

- `python tools/suggest_project_id.py` : Membuat saran `PROJECT_ID` acak.
- `python tools/check_sensors.py` : Memeriksa sensor Accelerometer & Gyroscope di Termux.
- `python tools/send_command.py start` : Mengirim perintah kontrol (`start`, `pause`, `resume`, `end`, `calibrate`, `snooze`, `time_scale`) dari CLI.
- `python tools/record_telemetry.py --out recordings/sesi.csv --duration 60` : Merekam data sensor dari MQTT ke CSV/JSONL untuk diunggah ke fitur **Mode Replay** di Dashboard.
- `python tools/run_scenarios.py` : Menjalankan 7 skenario uji secara instan di memori tanpa koneksi internet.

### Daftar Dokumen di Folder `docs/`:
- [`docs/SETUP.md`](docs/SETUP.md) : Instalasi Termux & Termux:API dari F-Droid, izin Android, wake-lock, dan troubleshooting.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) : Diagram arsitektur, sequence diagram, state machine, serta tabel topic dan payload.
- [`docs/ALGORITHM.md`](docs/ALGORITHM.md) : Rumus Processing 1 & 2, tabel ambang, tabel transisi state, dan rumus Movement Score.
- [`docs/TESTING.md`](docs/TESTING.md) : Panduan 7 skenario pengujian, tabel pencatatan hasil, dan eksperimen filter `desk`.
- [`docs/DESIGN_DECISIONS.md`](docs/DESIGN_DECISIONS.md) : Keputusan arsitektur, cara pakai ulang komponen domain, dan pernyataan orisinalitas.
- [`docs/PANDUAN_MEMBACA_KODE.md`](docs/PANDUAN_MEMBACA_KODE.md) : Peta modul dan urutan membaca alur kode dari sensor hingga aktuator.
- [`docs/SLIDES_DAN_DEMO.md`](docs/SLIDES_DAN_DEMO.md) : Kerangka slide presentasi, skrip video demo 3-4 menit, dan pembagian tugas kelompok.

*Catatan Cloud Opsional:* Dashboard dirancang berjalan lokal di laptop satu jaringan Wi-Fi/hotspot dengan pengguna. Bila kelompok ingin men-deploy dashboard ke Streamlit Community Cloud, cukup atur `PROJECT_ID` pada menu *Secrets* Streamlit tanpa mengubah kode.
