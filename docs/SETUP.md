# Panduan Penyiapan Perangkat Lengkap (Laptop, HP Android Termux, HP iOS / iPhone, & Simulasi)

Dokumen ini menjelaskan panduan instalasi dan penyiapan sistem **GESER** (*Gravity-tilt Estimation for Sedentary Event Reminders*) secara menyeluruh untuk:
1. **Laptop** (Windows, macOS, Linux) sebagai *Session Engine* dan *Streamlit Dashboard*.
2. **HP Android** (Termux + Termux:API) dengan dukungan deteksi sensor hardware otomatis.
3. **HP iOS / iPhone / iPad** menggunakan antarmuka *Browser Edge* berbasis WebSensor & WebSockets TLS.
4. **Laptop Standalone** (Mode Simulasi Penuh tanpa HP fisik).

---

## 1. Kebutuhan Sistem & Jaringan

### Kebutuhan Perangkat Keras
- **1 Laptop:** Menjalankan otak komputasi (`geser-engine`) dan visualisasi grafik (`streamlit`).
- **2 Perangkat Edge (Pilih kombinasi apa saja):**
  - HP A (*body*): Dimasukkan ke saku baju dada untuk mendeteksi gerakan & kemiringan tubuh.
  - HP B (*desk*): Diletakkan mendatar di atas meja untuk memfilter getaran/gebrakan meja.
  - *(Dapat menggunakan 2 HP Android, 1 Android + 1 iPhone, 2 iPhone, atau simulasi laptop)*.

### Kebutuhan Jaringan & Internet
- Koneksi internet yang mengizinkan port:
  - **TCP `8883`**: MQTT over TLS (digunakan oleh Python di Laptop & Termux).
  - **TCP `8884`**: MQTT over Secure WebSockets / WSS (digunakan oleh Browser Edge di iOS/Chrome).
- **Catatan Jaringan Kampus / Kantor:** Jika firewall Wi-Fi memblokir port 8883, hubungkan laptop dan semua HP ke **Hotspot / Tethering Wi-Fi** dari salah satu HP.
- **Sinkronisasi Waktu (NTP):** Pastikan pengaturan **Automatic Date & Time (NTP)** aktif di laptop dan kedua HP. Selisih jam tidak boleh lebih dari 30 detik.

---

## 2. Penyiapan di Laptop (Session Engine & Dashboard)

### A. Di Windows (PowerShell)

1. Buka **PowerShell** di folder repositori `geser`:
   ```powershell
   # 1. Berikan izin eksekusi skrip untuk sesi ini
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

   # 2. Buat virtual environment dengan Python 3.10 - 3.12 resmi Windows
   # (Gunakan py -3.12 atau py -m untuk menghindari konflik jika terpasang MSYS2/Git-Bash)
   py -3.12 -m venv .venv

   # 3. Aktifkan virtual environment
   .\.venv\Scripts\Activate.ps1

   # 4. Perbarui pip dan pasang semua dependensi
   python -m pip install --upgrade pip
   pip install -e ".[dashboard,dev]"

   # 5. Salin berkas konfigurasi lingkungan
   Copy-Item .env.example .env

   # 6. Hasilkan Project ID acak yang unik
   python tools/suggest_project_id.py
   ```

2. Buka berkas [`.env`](file:///d:/Projects/dematika/geser/.env) di editor teks, lalu ganti baris:
   ```ini
   PROJECT_ID=geser-kelompok-xxxx
   ```
   *(Gunakan nilai hasil dari perintah `suggest_project_id.py`).*

3. **Menonaktifkan Prompt Email Streamlit Pertama Kali (Opsional):**
   Agar Streamlit tidak berhenti meminta email saat pertama dijalankan:
   ```powershell
   if (!(Test-Path "$env:USERPROFILE\.streamlit")) { New-Item -ItemType Directory -Path "$env:USERPROFILE\.streamlit" -Force }
   Set-Content -Path "$env:USERPROFILE\.streamlit\credentials.toml" -Value "[general]`nemail = `"`""
   ```

---

### B. Di macOS / Linux (Bash / Zsh)

1. Buka terminal di folder `geser`:
   ```bash
   # 1. Buat dan aktifkan virtual environment
   python3 -m venv .venv
   source .venv/bin/activate

   # 2. Perbarui pip dan pasang paket
   pip install --upgrade pip
   pip install -e ".[dashboard,dev]"

   # 3. Salin berkas konfigurasi
   cp .env.example .env

   # 4. Hasilkan saran Project ID unik
   python tools/suggest_project_id.py
   ```

2. Buka berkas `.env` dan perbarui `PROJECT_ID` sesuai keluaran di terminal.

---

### C. Menjalankan Server & Dashboard di Laptop

Buka **2 terminal / tab terpisah** di laptop:

- **Terminal 1 (Session Engine):**
  ```powershell
  # Windows:
  .\.venv\Scripts\Activate.ps1
  geser-engine

  # Tips Uji Coba Cepat: Tambahkan --time-scale 30 agar 30 menit dicapai dalam 1 menit nyata
  # geser-engine --time-scale 30
  ```

- **Terminal 2 (Dashboard Streamlit):**
  ```powershell
  # Windows:
  .\.venv\Scripts\Activate.ps1
  streamlit run src/geser/dashboard/app.py
  ```
  Dashboard akan otomatis terbuka di peramban pada alamat:
  👉 **`http://localhost:8501`**

---

### D. Mode Simulasi Penuh di Laptop (Uji Coba Tanpa HP Fisik)

Jika Anda belum memiliki HP fisik atau ingin menguji logika sistem di laptop:
```powershell
# Buka terminal ke-3 untuk HP Body (simulasi diam / still):
.\.venv\Scripts\Activate.ps1
geser-edge --role body --simulate still

# Buka terminal ke-4 untuk HP Desk (simulasi meja diam):
.\.venv\Scripts\Activate.ps1
geser-edge --role desk --simulate still
```
*(Profil simulasi yang tersedia: `still` = diam normal, `fidget` = gelisah gerak-gerak kecil, `shake` = guncangan meja / reposisi besar)*.

---

## 3. Penyiapan di HP Android (Termux + Termux:API)

Metode ini menggunakan aplikasi **Termux** dan pendamping **Termux:API** untuk membaca sensor fisik perangkat secara *native*.

### Langkah 1: Pasang Termux & Termux:API dari F-Droid
> ⚠️ **PENTING:** Jangan menginstal Termux dari Google Play Store! Versi di Play Store sudah kedaluwarsa dan tidak kompatibel dengan API sensor.

1. Buka peramban di HP Android dan pasang **F-Droid** dari [https://f-droid.org](https://f-droid.org).
2. Di dalam F-Droid, cari dan pasang **2 aplikasi**:
   - **Termux**
   - **Termux:API**

### Langkah 2: Pengaturan Izin Android (Penting untuk Xiaomi/MIUI/Samsung/Oppo)
1. Buka **Pengaturan HP -> Aplikasi -> Kelola Aplikasi -> Termux:API**:
   - **Izin Aplikasi (Permissions):** Berikan izin **Sensor / Sensor Tubuh (Body Sensors)** dan **Aktivitas Fisik (Physical Activity)**.
   - **Mulai Otomatis (Autostart):** Aktifkan.
   - **Penghemat Baterai (Battery Saver):** Ubah ke **Tidak Ada Batasan (No Restrictions)**.
2. Buka **Pengaturan HP -> Aplikasi -> Kelola Aplikasi -> Termux**:
   - Ubah Penghemat Baterai ke **Tidak Ada Batasan**.
   - Di layar *Recent Apps* (Multitasking), kunci (*Lock*) aplikasi Termux agar tidak ditutup otomatis oleh Android saat layar mati.

### Langkah 3: Pasang Paket di Dalam Termux
Buka aplikasi Termux di HP, lalu jalankan:
```bash
pkg update && pkg upgrade -y
pkg install python git termux-api -y

# Cegah CPU tidur saat layar HP mati di dalam saku
termux-wake-lock
```

### Langkah 4: Kloning Repositori & Pasang GESER
```bash
git clone https://github.com/mohamadsolkhannawawi/geser.git geser
cd geser
pip install -e .
cp .env.example .env
```
Edit berkas `.env` (misalnya dengan `nano .env`) dan pastikan `PROJECT_ID` diisi **sama persis** dengan `PROJECT_ID` di laptop:
```ini
PROJECT_ID=geser-kelompok-xxxx
```

### Langkah 5: Penyesuaian Sensor Hardware Khusus (Contoh: Xiaomi LSM6DSOQ)
Periksa daftar sensor bawaan di HP Anda:
```bash
python tools/check_sensors.py
```
- Jika terminal menampilkan nama sensor khusus seperti `lsm6dsoq_acc` (akselerometer) dan `lsm6dsoq_gyro` (giroskop), tambahkan konfigurasi ini ke `.env` HP:
  ```bash
  echo "ACCEL_SENSOR=lsm6dsoq_acc" >> .env
  echo "GYRO_SENSOR=lsm6dsoq_gyro" >> .env
  ```
- Uji kembali kesiapan sensor:
  ```bash
  python tools/check_sensors.py
  ```
  *(Pastikan output mencetak `Berhasil! Sampel akselerometer: >0, giroskop: >0`).*

> 💡 **Tips Pembersihan Sensor:** Jika sensor terasa menggantung atau menghasilkan sampel 0, jalankan perintah reset:
> ```bash
> termux-sensor -c
> ```

### Langkah 6: Jalankan Peran Edge di HP Android
- **Di HP A (peran body - masukkan ke saku baju dada):**
  ```bash
  geser-edge --role body
  ```
- **Di HP B (peran desk - letakkan mendatar di atas meja):**
  ```bash
  geser-edge --role desk
  ```

---

## 4. Penyiapan di HP iOS (iPhone / iPad)

Karena iOS menerapkan *sandbox* keamanan yang ketat dan tidak mengizinkan Termux, perangkat iOS menggunakan klien web **Browser Edge** ([`browser_edge/index.html`](file:///d:/Projects/dematika/geser/browser_edge/index.html)).

Halaman ini memanfaatkan **W3C DeviceOrientation & DeviceMotion Web API** yang otomatis terhubung ke broker cloud HiveMQ via **Secure WebSockets TLS (`wss://broker.hivemq.com:8884/mqtt`)**.

### A. Persyaratan Wajib iOS Safari
1. **Wajib HTTPS / Localhost:** Apple Safari **memblokir** akses sensor gerakan pada halaman HTTP biasa. Halaman harus diakses melalui protokol **`https://`**.
2. **Izin Sensor iOS:** Di iOS 13 ke atas, browser meminta konfirmasi izin akses sensor gerak setiap kali tombol ditekan.

---

### B. Cara Menyajikan Halaman HTTPS untuk iPhone

Pilih salah satu dari 2 opsi termudah berikut:

#### Opsi 1: Menggunakan GitHub Pages (Paling Mudah & Tanpa Instalasi Tambahan)
1. Buka repositori Anda di GitHub di peramban komputer.
2. Masuk ke tab **Settings -> Pages**.
3. Pada bagian **Build and deployment -> Source**, pilih **Deploy from a branch**.
4. Pilih branch `main` dan folder `/ (root)` lalu klik **Save**.
5. Setelah beberapa detik, GitHub akan memberikan URL HTTPS resmi:
   `https://<username>.github.io/geser/browser_edge/`
6. Buka URL tersebut di **Safari iPhone** Anda!

#### Opsi 2: Menggunakan Cloudflare Tunnel / Ngrok dari Laptop
Jika ingin menyajikan langsung dari file lokal di laptop ke iPhone:
1. Jalankan server lokal di laptop (di folder `geser`):
   ```powershell
   python -m http.server 8000
   ```
2. Jalankan tunnel HTTPS gratis (misalnya Cloudflare Tunnel atau Ngrok):
   ```powershell
   # Menggunakan cloudflared:
   cloudflared tunnel --url http://localhost:8000
   ```
3. Salin URL HTTPS yang dihasilkan (misal `https://random-name.trycloudflare.com/browser_edge/`) dan buka di Safari iPhone.

---

### C. Langkah Menjalankan di Safari iPhone

1. Buka URL HTTPS `browser_edge/` di **Safari iOS**.
2. Masukkan **`PROJECT_ID`** yang **sama persis** dengan yang ada di laptop (contoh: `geser-kelompok-xxxx`).
3. Pilih peran perangkat:
   - Pilih **`body (Saku Baju Dada)`** untuk iPhone di saku baju.
   - Pilih **`desk (Atas Meja)`** untuk iPhone di meja.
4. Klik tombol **Hubungkan & Mulai Kirim**.
5. Saat muncul pop-up izin Safari:
   > *"browser_edge ingin mengakses sensor gerak dan orientasi"*
   > 👉 Pilih **Izinkan (Allow)**.
6. **Kalibrasi Awal:** Letakkan iPhone di posisi normal (di saku dada sambil duduk tegak), lalu klik tombol abu-abu **Kalibrasi Baseline (5 detik)**.
7. **Pengaturan Layar iPhone:**
   Buka **Settings iPhone -> Display & Brightness -> Auto-Lock**: Ubah ke **Never** (atau minimal 5 menit) agar browser tidak tertidur saat layar mati.

---

## 5. Ringkasan Skenario Penempatan Perangkat

| Skenario | Peran Body (Saku Dada) | Peran Desk (Atas Meja) | Catatan |
|---|---|---|---|
| **Android + Android** | Termux: `geser-edge --role body` | Termux: `geser-edge --role desk` | Paling ideal, aktuator getar (`vibrate`) bekerja penuh pada kedua HP. |
| **Android + iPhone** | Termux: `geser-edge --role body` | iPhone Safari: `browser_edge` (`desk`) | Body bergetar fisik lewat Termux, Desk menampilkan notifikasi via web. |
| **iPhone + Android** | iPhone Safari: `browser_edge` (`body`) | Termux: `geser-edge --role desk` | Body mengirim data via Safari, Desk bergetar/notifikasi via Termux. |
| **iPhone + iPhone** | iPhone A Safari: `browser_edge` (`body`) | iPhone B Safari: `browser_edge` (`desk`) | Menggunakan 2 iPhone via HTTPS GitHub Pages. |
| **Hanya Laptop** | Terminal 3: `--simulate still` | Terminal 4: `--simulate still` | Simulasi komputasi penuh tanpa membutuhkan HP fisik. |

---

## 6. Panduan Pemecahan Masalah (Troubleshooting)

| Gejala / Pesan Masalah | Penyebab Utama | Solusi Praktis |
|---|---|---|
| `The term '.\.venv\Scripts\Activate.ps1' is not recognized` | Python membuat folder ala Linux (`bin/`) karena memanggil Python dari MSYS2/Git-Bash di Windows. | Hapus `.venv` lama, lalu buat ulang dengan Python Windows resmi: `py -3.12 -m venv .venv`. |
| `Welcome to Streamlit! Email:` dan proses berhenti (*RuntimeStoppedError*) | Streamlit baru pertama kali dijalankan dan menunggu input email di terminal. | Jalankan skrip pembuat `credentials.toml` yang tercantum di Bagian 2A untuk melewatinya secara permanen. |
| `WARNING: Tidak ada sampel akselerometer pada jendela ini` | Termux belum berhasil membaca data hardware sensor HP. | 1. Berikan izin *Sensors* pada aplikasi **Termux:API** di Pengaturan HP.<br>2. Periksa nama sensor dengan `python tools/check_sensors.py`. Jika bukan `accelerometer`, setel `ACCEL_SENSOR` di `.env`. |
| `Sampel akselerometer: 0, giroskop: 0` | Layanan background sensor Android terkunci dari proses sebelumnya yang dihentikan mendadak. | Jalankan perintah pembersihan sensor di Termux: `termux-sensor -c`. |
| `GESER menolak berjalan: PROJECT_ID masih placeholder` | Berkas `.env` belum dibuat atau masih tertulis `geser-kelompok-GANTI`. | Jalankan `python tools/suggest_project_id.py` lalu salin hasilnya ke berkas `.env`. |
| iPhone Safari tidak mengeluarkan data / grafik tidak bergerak | Safari memblokir API sensor jika dibuka lewat HTTP biasa, atau izin sensor ditolak. | 1. Wajib gunakan **HTTPS** (via GitHub Pages atau tunnel).<br>2. Klik tombol **Hubungkan & Mulai Kirim** lalu klik **Izinkan** pada dialog izin sensor Safari. |
| Pesan ditolak: `t_ms terlalu jauh dari waktu engine` | Jam HP dan jam Laptop berselisih lebih dari 30 detik. | Aktifkan pengaturan **Automatic Date & Time (NTP)** pada Laptop dan semua HP. |
| Koneksi ke `broker.hivemq.com:8883` gagal / Timeout | Port 8883 diblokir oleh firewall Wi-Fi lokal / kampus. | Gunakan fitur **Tethering / Hotspot Wi-Fi** dari salah satu HP untuk menyambungkan semua perangkat. |
| Getaran tidak terasa di HP *body* pada Level 1 | Sesuai desain algoritma, Level 1 hanya mengirim pengingat visual ke HP *desk* dan Dashboard. | Getaran pendek baru dimulai pada **Level 2** (setelah 45 menit / disesuaikan `TIME_SCALE`), dan getaran panjang di **Level 3**. Pastikan mode *Do Not Disturb* tidak aktif. |
