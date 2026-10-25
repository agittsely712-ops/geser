# Panduan Membaca Kode Sumber GESER

Dokumen ini membantu anggota kelompok dan penguji memahami organisasi modul serta melacak alur satu pesan dari sensor HP hingga menjadi pengingat.

---

## 1. Peta Lapisan Modul (`src/geser/`)

| Folder / Modul | Tanggung Jawab Utama | Ketergantungan Luar |
|---|---|---|
| `settings/` | Memuat `configs/default.yaml` dan `.env`, memvalidasi `PROJECT_ID` dan rentang angka konfigurasi. | `PyYAML` |
| `domain/` | **Inti Murni:** operasi vektor 3D (`geometry.py`), Processing 1 (`features.py`), Processing 2 & noise floor (`stillness.py`), state machine (`states.py`), jadwal pengingat (`reminder_policy.py`), dan skor (`scoring.py`). | **Tidak ada** (100% Python standar) |
| `messaging/` | Pemetaan nama topic (`topics.py`), validasi ketat JSON (`codec.py`), dan konversi CSV/JSONL (`recording.py`). | `domain`, `settings` |
| `ports/` | Kontrak antarmuka `Protocol`: `SensorReader`, `MessageBus`, `Clock`, `Actuator`. | `domain` |
| `adapters/` | Implementasi konkret untuk Termux (`termux_sensor.py`, `termux_actuator.py`), MQTT (`mqtt_bus.py`), dan simulasi (`simulated_sensor.py`, `memory_bus.py`). | `paho-mqtt`, `subprocess` |
| `services/` | Orkestrator aplikasi: `EdgeNode` (`edge_node.py`) dan `SessionEngine` (`session_engine.py`). | `domain`, `messaging`, `ports` |
| `apps/` | Titik masuk CLI `geser-edge` dan `geser-engine`. | Semua lapisan di atas |
| `dashboard/` | Antarmuka pengguna web berbasis Streamlit (`app.py`, `feed.py`, `charts.py`, `views/`). | `streamlit`, `pandas` |

---

## 2. Urutan Membaca yang Disarankan

1. **Mulai dari `configs/default.yaml` dan `src/geser/domain/models.py`**: Pahami benda data yang mengalir di dalam sistem (`SensorBatch`, `WindowFeatures`, `Telemetry`, `SessionSnapshot`).
2. **Baca `src/geser/domain/features.py`**: Lihat bagaimana sampel mentah 2 detik dirangkum menjadi vektor gravitasi dan angka getaran (Processing 1).
3. **Baca `src/geser/domain/stillness.py` dan `states.py`**: Lihat bagaimana durasi diam dihitung terhadap `anchor` dan bagaimana prioritas status ditentukan (Processing 2).
4. **Baca `src/geser/services/edge_node.py` dan `session_engine.py`**: Perhatikan bagaimana kedua layanan ini menghubungkan domain murni dengan port `MessageBus` dan `Actuator`.
5. **Baca `src/geser/dashboard/app.py`**: Lihat bagaimana data dari MQTT ditampilkan secara *live* tanpa memblokir thread UI.

---

## 3. Alur Satu Pesan dari Sensor Sampai Pengingat

1. **Cuplik Sensor (HP):** `TermuxSensor.read_batch(2.0)` mengumpulkan sampel akselerometer dan giroskop selama 2 detik menjadi `SensorBatch`.
2. **Processing 1 (HP):** `EdgeNode.step()` memanggil `WindowFeatureExtractor.extract(batch)` untuk menghasilkan `WindowFeatures` (`gravity`, `tilt_deg`, `accel_dev_rms`, `gyro_path_rad`).
3. **Kirim Telemetry (HP -> Broker):** `codec.encode_telemetry()` mengubah data menjadi JSON dan `MqttBus.publish()` mengirimkannya ke `geser/<PROJECT_ID>/edge/body/telemetry` dengan QoS 1.
4. **Validasi Masuk (Engine):** `SessionEngine._on_edge_message()` mendekode JSON lewat `codec.decode_telemetry()`, memeriksa kesesuaian waktu ($\le 30$ detik) dan kenaikan `n_msg` (`SequenceGuard`).
5. **Processing 2 & Fusi (Engine):** `SessionEngine._on_body_window()` memeriksa apakah `desk` terguncang (`_desk_disturbed`). Jika aman, `StillnessTracker.observe()` mengevaluasi apakah pengguna diam (`STILL`) atau berpindah posisi (`REPOSITION`).
6. **Transisi State & Jadwal Pengingat (Engine):** `_refresh()` memanggil fungsi murni `transition()`. Bila status berada di `STILL_LONG` / `STILL_VERY_LONG` / `STILL_CRITICAL`, `ReminderScheduler.evaluate()` menentukan apakah pengingat baru perlu dikirim ke topic `reminders`.
7. **Aktuasi (HP & Dashboard):** `EdgeNode._on_reminder()` menerima pesan dari topic `reminders`, menyusun rencana lewat `plan_for()`, lalu memicu `termux-vibrate` di HP `body` dan `termux-notification` di HP `desk` (atau membatalkannya bila event bernilai `cleared`).
