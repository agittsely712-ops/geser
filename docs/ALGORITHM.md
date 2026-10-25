# Dokumentasi Algoritma & Pengolahan Data GESER

Kategori algoritma yang digunakan adalah **algoritma lain: rule-based dengan state machine**. Perhitungan rata-rata dan simpangan baku pada penentuan *noise floor* merupakan statistik deskriptif sederhana dan bukan kecerdasan buatan (AI/ML).

> **Penafian:** Sistem hanya memperkirakan dari gerakan perangkat, bukan mengukur postur dan bukan alat medis.

---

## 1. Processing 1: Ekstraksi Fitur di Edge (`src/geser/domain/features.py`)

Setiap jendela berdurasi `window_s = 2.0` detik (dengan laju cuplik sekitar 10 Hz atau ~20 sampel per jendela), node edge membaca akselerometer $\mathbf{a}_i = (a_x, a_y, a_z)$ dalam $\text{m/s}^2$ dan giroskop $\boldsymbol{\omega}_i = (\omega_x, \omega_y, \omega_z)$ dalam $\text{rad/s}$:

1. **Penyaringan Low-Pass Vektor Gravitasi (`GravityFilter`):**
   Komponen gravitasi dipisahkan dari percepatan gerak sesaat dengan filter eksponensial ($\alpha = 0.9$):
   $$\mathbf{s}_i = \alpha \mathbf{s}_{i-1} + (1 - \alpha)\mathbf{a}_i, \quad \mathbf{g} = \frac{\mathbf{s}_N}{\|\mathbf{s}_N\|}$$
2. **Rumus Sudut Antar Dua Vektor Satuan (`angle_deg`):**
   $$\text{angle}(\mathbf{u}, \mathbf{v}) = \text{degrees}\left(\arccos\left(\text{clip}(\mathbf{u} \cdot \mathbf{v}, -1.0, 1.0)\right)\right)$$
   - `tilt_step_deg` $= \text{angle}(\mathbf{g}_t, \mathbf{g}_{t-1})$ (perubahan kemiringan terhadap jendela sebelumnya).
   - `tilt_deg` $= \text{angle}(\mathbf{g}_t, \mathbf{g}_{\text{baseline}})$ bila perangkat sudah dikalibrasi selama 5 detik (rata-rata arah gravitasi selama 3 jendela kalibrasi).
3. **Getaran di Luar Gravitasi (`accel_dev_rms`):**
   $$\text{accel\_dev\_rms} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} \left(\|\mathbf{a}_i\| - 9.81\right)^2}$$
4. **Akumulasi Lintasan Sudut Giroskop (`gyro_path_rad`):**
   $$\text{gyro\_path\_rad} = \sum_{i=2}^{N} \|\boldsymbol{\omega}_i\| \cdot \Delta t_i \quad (\text{untuk } 0 < \Delta t_i \le 0.5\text{ s})$$

---

## 2. Processing 2: Pelacak Diam, Fusi Meja, dan Noise Floor di Engine (`src/geser/domain/stillness.py`)

Engine memelihara vektor gravitasi acuan posisi duduk saat itu yang disebut **`anchor`** ($\mathbf{g}_{\text{anchor}}$).

### A. Fusi Penolakan Gangguan Meja (`desk`)
Sebelum jendela `body` dievaluasi, Engine memeriksa jendela terakhir dari `desk`:
- Bila selisih waktu terima `now_ms - desk.received_ms <= 5000` ms **dan** `desk.accel_dev_rms >= 0.60`, maka meja dinyatakan sedang terguncang (`DISTURBED`).
- Jendela `body` pada saat itu **diabaikan** (tidak menambah durasi diam dan tidak memicu reset posisi palsu akibat meja digebrak/tersenggol).

### B. Noise Floor Adaptif (`NoiseFloor`)
Pada 60 detik nyata pertama sejak sesi dimulai (`SETTLING`), semua jendela tenang (`gyro_path_rad < 0.15` dan bukan reposisi) dikumpulkan nilai `accel_dev_rms`-nya:
$$\text{limit}_{\text{personal}} = \text{clip}\left(\mu + k \cdot \sigma, \; 0.10, \; 0.40\right), \quad k = 3.0$$
Sebelum 60 detik selesai (atau bila sampel $< 5$), digunakan nilai awal `0.25` $\text{m/s}^2$.

### C. Penilaian Jendela (`StillnessTracker.observe`)
Untuk setiap jendela `body` yang valid dengan sudut ke anchor $\theta_{\text{anchor}} = \text{angle}(\mathbf{g}_t, \mathbf{g}_{\text{anchor}})$:
1. **Reposition (`Verdict.REPOSITION`):**
   Terjadi bila $\theta_{\text{anchor}} \ge 15.0^\circ$ **ATAU** jumlah `gyro_path_rad` dalam jendela geser 10 detik terakhir $\ge 0.80\text{ rad}$.
   - Efek: `still_s` di-reset ke `0`, `anchor` diperbarui ke $\mathbf{g}_t$, pengingat aktif dibatalkan otomatis (*auto-clear*), dan skor ditambah bonus.
2. **Diam (`Verdict.STILL`):**
   Terjadi bila:
   - $\theta_{\text{anchor}} < 10.0^\circ$ (atau $< 14.0^\circ$ dengan histeresis $+4.0^\circ$ bila jendela sebelumnya sudah berstatus diam), **DAN**
   - `accel_dev_rms` $< \text{limit}_{\text{personal}}$, **DAN**
   - `gyro_path_rad` $< 0.15\text{ rad}$.
   - Efek: durasi diam bertambah sebesar `window_s` (`2.0` detik).
3. **Gerak Kecil (`Verdict.NEUTRAL`):**
   Gerakan kecil di antara ambang diam dan ambang reposisi tidak menambah durasi diam, tetapi **tidak mereset** timer yang sudah terkumpul.

---

## 3. Tabel Ambang Awal (`configs/default.yaml`)

| Parameter | Nilai Awal | Satuan | Keterangan |
|---|---|---|---|
| `edge.window_s` | `2.0` | detik | Durasi satu jendela ekstraksi fitur |
| `stillness.still_angle_deg` | `10.0` | derajat | Batas sudut terhadap anchor agar dihitung diam |
| `stillness.exit_hysteresis_deg` | `4.0` | derajat | Histeresis keluar dari kondisi diam (total 14 derajat) |
| `stillness.reposition_angle_deg` | `15.0` | derajat | Sudut perpindahan posisi yang mereset timer |
| `stillness.accel_dev_max` | `0.25` | $\text{m/s}^2$ | Ambang getaran awal sebelum noise floor selesai |
| `stillness.gyro_path_max_rad` | `0.15` | rad | Batas rotasi maksimum per jendela saat diam |
| `stillness.reposition_gyro_rad` | `0.80` | rad | Akumulasi rotasi 10 detik penanda ganti posisi |
| `fusion.desk_disturb_accel_rms` | `0.60` | $\text{m/s}^2$ | Ambang getaran meja penanda gangguan (`DISTURBED`) |
| `fusion.pair_gap_s` | `5.0` | detik | Jendela waktu pencocokan pesan `desk` dan `body` |
| `fusion.data_gap_s` | `6.0` | detik | Batas celah waktu sebelum status menjadi `NO_DATA` |
| `lean.angle_deg` | `25.0` | derajat | Sudut condong jauh dari baseline kalibrasi |
| `lean.duration_min` | `5.0` | menit | Durasi condong sebelum berstatus `LEAN_DRIFT` |
| `reminders.level1_min` | `30.0` | menit | Ambang pengingat Level 1 (`STILL_LONG`) |
| `reminders.level2_min` | `45.0` | menit | Ambang pengingat Level 2 (`STILL_VERY_LONG`) |
| `reminders.level3_min` | `60.0` | menit | Ambang pengingat Level 3 (`STILL_CRITICAL`) |

---

## 4. Tabel Prioritas Transisi State (`src/geser/domain/states.py`)

Fungsi murni `transition(facts, thresholds)` mengevaluasi kondisi dari prioritas tertinggi ke terendah:

| Prioritas | Kondisi Fakta (`StateFacts`) | State Hasil | Aktuasi / Perilaku |
|---|---|---|---|
| 1 | `calibrating == True` | `CALIBRATING` | Mengambil rata-rata gravitasi baseline (5 detik) |
| 2 | `ended == True` | `ENDED` | Sesi diakhiri oleh pengguna |
| 3 | `active == False` | `IDLE` | Menunggu perintah `start` |
| 4 | `paused == True` | `ON_BREAK` | Sesi dijeda sementara |
| 5 | `no_data == True` (celah > 6 detik) | `NO_DATA` | Aliran data `body` terputus |
| 6 | `disturbed == True` | `DISTURBED` | Meja terguncang, jendela diabaikan |
| 7 | `still_scaled_s >= 60 menit` | `STILL_CRITICAL` | Pengingat L3: getar panjang berulang + notifikasi |
| 8 | `still_scaled_s >= 45 menit` | `STILL_VERY_LONG` | Pengingat L2: getar pendek `body` + notifikasi `desk` |
| 9 | `still_scaled_s >= 30 menit` | `STILL_LONG` | Pengingat L1: kartu dashboard + notifikasi `desk` |
| 10 | `lean_scaled_s >= 5 menit` | `LEAN_DRIFT` | Kemiringan >= 25 derajat dari baseline cukup lama |
| 11 | `still_scaled_s >= 5 menit` | `STILL` | Posisi tubuh tercatat diam |
| 12 | `settling == True` (< 60 detik nyata) | `SETTLING` | Mengumpulkan sampel noise floor adaptif |
| 13 | Lainnya | `ACTIVE` | Pengguna baru bergerak atau belum lama diam |

---

## 5. Rumus Movement Score (`src/geser/domain/scoring.py`)

Skor dimulai dari $S_0 = 100.0$ dan selalu dijepit pada rentang $[0, 100]$:
- Setiap jendela dengan durasi menit skala $\Delta m = \frac{\text{window\_s} \times \text{TIME\_SCALE}}{60}$:
  - Jika status berada di `STILL_LONG`, `STILL_VERY_LONG`, atau `STILL_CRITICAL`:
    $$S \leftarrow \text{clip}(S - 3.0 \times \Delta m, 0, 100)$$
  - Jika status berada di `LEAN_DRIFT`:
    $$S \leftarrow \text{clip}(S - 1.0 \times \Delta m, 0, 100)$$
- Setiap kali terdeteksi `reposition` setelah sebelumnya sempat diam:
  $$S \leftarrow \text{clip}(S + 5.0, 0, 100)$$

---

## 6. Keterbatasan Sistem
1. Sistem hanya membaca orientasi dan percepatan HP di saku baju dada; jika saku baju terlalu longgar, sudut kemiringan HP dapat bergeser sendiri.
2. Gerakan kaki atau tangan yang tidak mengubah kemiringan torso maupun getaran dada tidak terdeteksi oleh HP `body`.
3. Validasi anti-replay mensyaratkan jam sistem antara HP dan laptop sinkron (selisih maksimal 30 detik).
