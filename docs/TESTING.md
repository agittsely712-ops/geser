# Panduan Pengujian 7 Skenario & Eksperimen GESER

## Status Tes (Pernyataan Jujur)
- Pemeriksaan kompilasi (`python -m compileall src`) dan uji impor modul telah diverifikasi saat paket dibangun.
- **Unit test di `tests/unit/` serta pengujian lapangan dengan 2 HP Android belum dijalankan oleh penulis kode.** Pengujian dilakukan sendiri oleh pengguna menggunakan panduan dan tabel di bawah ini.

---

## 1. Menjalankan Tes Otomatis & Simulasi Cepat di Laptop

Sebelum menguji dengan 2 HP fisik, Anda dapat memverifikasi logika domain dan skenario mesin sesi di laptop:
```powershell
# Menjalankan unit test domain murni dan codec
pytest

# Menjalankan simulasi 7 skenario instan di memori (tanpa internet)
python tools/run_scenarios.py
```

---

## 2. Prosedur 7 Skenario Pengujian dengan Perangkat (Gunakan `TIME_SCALE = 30`)

Jalankan `geser-engine --time-scale 30`, aktifkan kedua HP (`geser-edge --role body` dan `geser-edge --role desk`), lalu buka Dashboard Streamlit. Dengan `TIME_SCALE = 30`, **1 menit waktu skala setara dengan 2 detik waktu nyata** (ambang 30 menit dicapai dalam 60 detik nyata).

### Panduan Langkah 7 Skenario:
1. **Diam sampai L1 dan L2 dengan `TIME_SCALE`:** Klik **Start**, duduk diam selama 60 detik nyata (mencapai 30 menit skala -> `STILL_LONG` / L1, notifikasi muncul di HP `desk`), lanjutkan diam hingga 90 detik nyata (45 menit skala -> `STILL_VERY_LONG` / L2, HP `body` bergetar pendek).
2. **Ganti posisi lalu Auto-Clear:** Saat pengingat L2 masih aktif, miringkan badan atau berdiri sebentar (perubahan sudut >= 15 derajat) sementara meja tetap tenang. Pastikan pengingat otomatis dibatalkan (`cleared`) di kedua HP dan timer kembali ke 0.
3. **Gerak kecil tidak mereset timer:** Duduk diam hingga timer berjalan beberapa menit skala, lalu miringkan badan sedikit saja (~5 derajat) dan kembali. Pastikan timer diam tidak kembali ke 0.
4. **Meja diguncang menjadi `DISTURBED`:** Saat pengguna duduk diam, ketuk atau guncang meja di dekat HP `desk` (`accel_dev_rms >= 0.6`). Pastikan status berubah ke `DISTURBED` dan tidak mereset timer secara palsu.
5. **HP `desk` dipindah:** Angkat dan geser posisi HP `desk` di meja ketika pengguna sedikit bergerak di kursi. Pastikan selama `desk` bergerak kuat, gerakan tersebut ditolak sebagai gangguan.
6. **HP `body` dilepas / dihentikan menjadi `NO_DATA`:** Tekan `Ctrl+C` pada Termux HP `body` (atau matikan koneksi datanya) selama lebih dari 6 detik. Pastikan status di Dashboard berubah menjadi `NO_DATA` dan indikator kehadiran `body` menjadi `OFFLINE`.
7. **Condong lama menjadi `LEAN_DRIFT`:** Duduk tegak dan klik **Kalibrasi 5 dtk**. Setelah kalibrasi selesai, bungkukkan/miringkan badan >= 25 derajat dan tahan selama >= 10 detik nyata (5 menit skala). Pastikan status beralih ke `LEAN_DRIFT`.

---

## 3. Template Tabel Hasil Pengujian (Diisi oleh Kelompok)

| No | Skenario | Percobaan ke- | Deteksi Benar (Ya/Tidak) | Alarm/Reset Palsu | Latensi Pengingat / Transisi (ms) | Catatan Pengamatan |
|---|---|---|---|---|---|---|
| 1 | Diam sampai L1 & L2 (`TIME_SCALE=30`) | 1..3 | | | | |
| 2 | Ganti posisi -> Auto-Clear | 1..3 | | | | |
| 3 | Gerak kecil (< 10 deg) tidak reset | 1..3 | | | | |
| 4 | Meja diguncang -> `DISTURBED` | 1..3 | | | | |
| 5 | HP `desk` dipindah | 1..3 | | | | |
| 6 | HP `body` mati > 6 dtk -> `NO_DATA` | 1..3 | | | | |
| 7 | Condong >= 25 deg lama -> `LEAN_DRIFT` | 1..3 | | | | |

---

## 4. Eksperimen Pembanding: Dengan vs Tanpa Filter `desk`

Tujuan eksperimen ini adalah membuktikan manfaat menggunakan sensor kedua di meja (`desk`).
1. **Dengan Filter `desk` (Default):** Jalankan `geser-engine --time-scale 30`. Saat subjek duduk di kursi dan meja diguncang 10 kali, catat berapa kali guncangan meja salah terdeteksi sebagai perubahan posisi atau gangguan.
2. **Tanpa Filter `desk`:** Hentikan engine, lalu jalankan ulang dengan flag `geser-engine --time-scale 30 --no-desk-filter`. Lakukan 10 kali guncangan meja yang sama dan bandingkan hasilnya pada tabel berikut:

| Mode Konfigurasi Engine | Jumlah Uji Guncangan Meja | Jumlah Status `DISTURBED` Tertangkap | Jumlah Reset/Gangguan Palsu pada Timer Body |
|---|---|---|---|
| **Dengan Filter Desk** (`geser-engine`) | 10 | ... | ... |
| **Tanpa Filter Desk** (`geser-engine --no-desk-filter`) | 10 | ... | ... |
