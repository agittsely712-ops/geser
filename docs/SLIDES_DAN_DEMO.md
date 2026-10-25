# Kerangka Slide Presentasi, Skrip Video Demo, & Pemetaan Rubrik

## 1. Kerangka Slide Presentasi (PPT Dokumentasi)

1. **Slide 1 - Sampul & Identitas**: Judul **GESER** (*Gravity-tilt Estimation for Sedentary Event Reminders*), tagline *"Geser dikit, yuk"*, nama anggota kelompok (3-4 orang).
2. **Slide 2 - Masalah, Ide Solusi, & Disclaimer**: Masalah duduk statis terlalu lama saat mengerjakan tugas; solusi pemantauan dua perangkat (`body` di saku dada & `desk` di meja) dengan pengingat bertahap dan *auto-clear*; penafian tegas bahwa sistem hanya memperkirakan dari gerakan perangkat dan bukan alat medis.
3. **Slide 3 - Arsitektur 2 Edge, Cloud MQTT, & Satu Jaringan**: Diagram aliran data 2 arah antara 2 HP Android (Termux), broker publik HiveMQ TLS (`8883`), `geser-engine`, dan Dashboard Streamlit lokal.
4. **Slide 4 - Sensor & Processing 1 (di Edge)**: Pemanfaatan Accelerometer + Gyroscope, penyaringan low-pass gravitasi, perhitungan `tilt_deg`, `tilt_step_deg`, `accel_dev_rms`, dan `gyro_path_rad` per jendela 2 detik.
5. **Slide 5 - Processing 2 & Algoritma State Machine (di Engine)**: Kategori algoritma (*rule-based dengan state machine*), noise floor adaptif 60 detik, fusi penolakan gangguan meja (`desk`), 13 status sesi, dan rumus *Movement Score*.
6. **Slide 6 - Protokol Komunikasi Cloud & Keamanan**: Tabel topic `geser/<PROJECT_ID>/...`, penggunaan QoS 1, Retained message, Last Will (`online`/`offline`), serta validasi skema dan anti-shell injection.
7. **Slide 7 - Pengujian 7 Skenario & Eksperimen Filter Desk**: Tabel hasil pengujian akurasi deteksi, latensi, serta perbandingan dengan dan tanpa filter `desk`.
8. **Slide 8 - Keterbatasan & Tautan Kode GitHub**: Keterbatasan mekanis saku pakaian, syarat sinkronisasi waktu NTP, dan tautan repositori GitHub.

---

## 2. Skrip Video Demo (Durasi 3 sampai 4 Menit dengan `TIME_SCALE = 30`)

- **Menit 00:00 - 00:35 (Pembuka & Perangkat):**
  Tampilkan masalah mahasiswa duduk terlalu lama. Perlihatkan perangkat fisik: HP A (`body`) dimasukkan ke saku baju dada, HP B (`desk`) diletakkan di atas meja, serta layar laptop yang menampilkan `geser-engine` dan Dashboard Streamlit. Sebutkan disclaimer non-medis.
- **Menit 00:35 - 01:20 (Kontrol 2 Arah, Start, & Kalibrasi):**
  Dari Dashboard Streamlit, atur `TIME_SCALE` ke **30** (jelaskan bahwa 30 menit diringkas menjadi 1 menit nyata untuk demo). Klik **Start**, lalu klik **Kalibrasi 5 dtk** sambil duduk tegak. Tunjukkan grafik kemiringan dan getaran bergerak *real-time* di tab **Timeline**.
- **Menit 01:20 - 02:00 (Uji Fusi Penolakan Gangguan Meja):**
  Saat pengguna duduk diam, ketuk/guncang meja tempat HP `desk` berada. Tunjukkan status di Dashboard berubah menjadi **`DISTURBED`** dan jelaskan bahwa gerakan meja ditolak sehingga tidak mereset timer diam secara keliru.
- **Menit 02:00 - 03:00 (Pengingat Bertahap L1 & L2):**
  Biarkan pengguna duduk diam hingga timer skala melewati 30 menit (60 detik nyata -> **Level 1**: tunjukkan notifikasi muncul di HP `desk`) dan 45 menit (90 detik nyata -> **Level 2**: tunjukkan HP `body` bergetar pendek dan notifikasi diperbarui).
- **Menit 03:00 - 03:45 (Reposition & Auto-Clear + Ringkasan CSV):**
  Pengguna berdiri atau berganti posisi duduk yang jelas (>= 15 derajat). Tunjukkan status langsung kembali ke **`ACTIVE`**, pesan **`cleared`** membatalkan pengingat di kedua HP secara otomatis, dan *Movement Score* mendapat bonus. Akhiri sesi dengan klik **End** dan unduh CSV di tab **Ringkasan Sesi**.

---

## 3. Pemetaan terhadap Rubrik Tugas Kuliah (Total 100 Poin)

| Komponen Rubrik | Bobot | Implementasi pada Proyek GESER |
|---|---|---|
| Ide dan Orisinalitas | 20 | Fusi 2 HP (`body` saku dada + `desk` penolak gangguan meja) dengan pengingat bertahap dan *auto-clear* saat berganti posisi. |
| Arsitektur | 15 | 2 edge fisik, masing-masing 2 sensor (Accelerometer + Gyroscope), arsitektur *Ports & Adapters* bersih, komunikasi 2 arah penuh. |
| Processing & Algoritma | 20 | Processing 1 di edge (vektor gravitasi, sudut kemiringan, RMS, lintasan giroskop) + Processing 2 di engine (anchor stillness, noise floor adaptif, fusi meja, 13-state FSM). |
| Komunikasi Cloud | 15 | MQTT over TLS (`broker.hivemq.com:8883`), QoS 1, Retained session & presence, Last Will, validasi payload ketat. |
| Pengujian & Demo | 15 | Alat `tools/run_scenarios.py`, `tools/record_telemetry.py`, dukungan `TIME_SCALE`, dan protokol 7 skenario + eksperimen filter `desk`. |
| Dokumentasi | 15 | `README.md` ringkas + 7 dokumen terstruktur di `docs/` lengkap dengan diagram Mermaid dan panduan troubleshooting. |

---

## 4. Usulan Pembagian Tugas Kelompok (3 sampai 4 Anggota)

- **Anggota 1 (Edge & Sensor):** Menyiapkan kedua HP Android (Termux + Termux:API), menguji Processing 1 (`features.py`), dan mendemonstrasikan aktuator getar/notifikasi.
- **Anggota 2 (Engine & Algoritma):** Mengelola `SessionEngine`, menjelaskan aturan Processing 2 (`stillness.py`), state machine (`states.py`), dan menjalankan eksperimen dengan/tanpa filter `desk`.
- **Anggota 3 (Cloud MQTT & Dashboard):** Menjelaskan skema topic/codec MQTT TLS, mengoperasikan kontrol 2 arah pada Dashboard Streamlit, serta merekam CSV/JSONL sesi.
- **Anggota 4 (Pengujian & Presentasi/Bila 4 Orang):** Memimpin pelaksanaan 7 skenario pengujian di `docs/TESTING.md`, menyusun slide PPT, dan mengarahkan perekaman video demo.
