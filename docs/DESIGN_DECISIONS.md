# Keputusan Desain, Cara Pakai Ulang, dan Pernyataan Orisinalitas

## 1. Keputusan Penting & Alasannya

1. **Arsitektur Ports and Adapters (Hexagonal):**
   Seluruh aturan bisnis dan rumus fisika ditempatkan di `src/geser/domain/` tanpa satupun `import` ke pustaka jaringan (`paho-mqtt`), UI (`streamlit`), maupun proses sistem (`subprocess`). Komunikasi ke dunia luar diabstraksikan melalui `Protocol` di `src/geser/ports/interfaces.py` (`SensorReader`, `MessageBus`, `Clock`, `Actuator`).
   *Alasan:* Memudahkan pengujian deterministik di memori (`MemoryBus` + `ManualClock`) dan menjaga agar perubahan antarmuka perangkat keras tidak merusak algoritma inti.

2. **Pengiriman Fitur per Jendela 2 Detik (Bukan Data Mentah):**
   Processing 1 dijalankan langsung di perangkat edge (HP), sehingga jaringan hanya menerima ringkasan 13 field JSON setiap 2 detik.
   *Alasan:* Menghemat baterai dan kuota data, memperkecil latensi broker publik, serta menjaga privasi pengguna.

3. **Keamanan pada Broker Publik (`broker.hivemq.com:8883`):**
   Broker publik tidak memakai autentikasi username/password. Oleh karena itu:
   - Koneksi dienkripsi memakai TLS (`certifi`).
   - `PROJECT_ID` wajib diganti dari placeholder agar ruang nama topic tidak bertabrakan antar kelompok.
   - `messaging/codec.py` menolak field tak dikenal, nilai `NaN`/`Inf`, selisih jam $> 30$ detik, dan nomor urut `n_msg` yang tidak naik.
   - `TermuxActuator` memanggil `subprocess.run([...])` sebagai daftar argumen tanpa `shell=True`, sehingga teks dari jaringan tidak pernah bisa dieksekusi sebagai perintah shell.

---

## 2. Daftar Field Payload Telemetry Final

Nama field payload telemetry yang dibakukan pada skema v1:
`v`, `device`, `run`, `n_msg`, `t_ms`, `window_s`, `samples`, `gravity`, `tilt_deg`, `tilt_step_deg`, `accel_dev_rms`, `gyro_path_rad`, `calibrated`.

---

## 3. Cara Menggunakan Ulang Komponen Domain di Proyek Lain

Karena paket `geser` dipasang standar lewat `pyproject.toml`, modul domain dapat langsung diimpor oleh proyek Python lain tanpa menjalankan MQTT atau Streamlit:

```python
from geser.domain.stillness import StillnessRules, StillnessTracker, Verdict

rules = StillnessRules(
    still_angle_deg=10.0,
    exit_hysteresis_deg=4.0,
    reposition_angle_deg=15.0,
    gyro_path_max_rad=0.15,
    reposition_gyro_rad=0.8,
    reposition_gyro_window_s=10.0,
)
tracker = StillnessTracker(rules)

verdict = tracker.observe(
    (0.0, 0.0, 1.0),
    accel_dev_rms=0.05,
    accel_dev_limit=0.25,
    gyro_path_rad=0.02,
    window_s=2.0,
    at_s=2.0,
)
assert verdict is Verdict.STILL
print("Durasi diam (detik):", tracker.still_s)
```

---

## 4. Pernyataan Orisinalitas

Proyek **GESER** dirancang dari awal dengan struktur berlapis (`settings`, `domain`, `messaging`, `ports`, `adapters`, `services`, `apps`, `dashboard`), skema topic, kontrak payload, serta mekanisme fusi dua perangkat (`body` di saku dada dan `desk` di atas meja) yang orisinal. Tidak ada kode, nama variabel, struktur folder, maupun teks yang disalin dari proyek contoh perkuliahan.
