# Arsitektur Sistem & Spesifikasi Komunikasi GESER

> **Penafian:** Sistem hanya memperkirakan durasi diam dan kemiringan dari gerakan perangkat, bukan mengukur postur tubuh dan bukan alat medis.

---

## 1. Diagram Arsitektur Komponen

```mermaid
flowchart LR
    subgraph Edge_Layer [Dua Perangkat Edge Fisik]
        Body[HP A: body
Di Saku Baju Dada
Sensor: Accel + Gyro
Aktuator: Getar]
        Desk[HP B: desk
Di Atas Meja
Sensor: Accel + Gyro
Aktuator: Notifikasi]
    end

    subgraph Cloud_Layer [Cloud MQTT Broker]
        Broker[(HiveMQ Public Broker
broker.hivemq.com:8883 TLS
wss://...:8884/mqtt)]
    end

    subgraph App_Layer [Laptop Pengguna - Satu Jaringan]
        Engine[Session Engine
geser-engine
Processing 2, Fusi, FSM]
        Dash[Dashboard Streamlit
Monitoring & Kontrol]
    end

    Body -- "telemetry (QoS 1)
presence (Retained)" --> Broker
    Desk -- "telemetry (QoS 1)
presence (Retained)" --> Broker
    Broker -- "telemetry & presence" --> Engine
    Broker -- "telemetry, session, reminders, events" --> Dash
    Engine -- "session (Retained)
reminders & events (QoS 1)" --> Broker
    Broker -- "reminders & control" --> Body
    Broker -- "reminders & control" --> Desk
    Dash -- "control (QoS 1)" --> Broker
    Broker -- "control" --> Engine
```

---

## 2. Diagram Urutan Komunikasi 2 Arah (Sequence Diagram)

```mermaid
sequenceDiagram
    participant UI as Dashboard Streamlit
    participant B as HiveMQ Broker (TLS)
    participant E as Session Engine
    participant Body as Edge: body
    participant Desk as Edge: desk

    Body->>B: Publish edge/body/presence = "online" (retained)
    Desk->>B: Publish edge/desk/presence = "online" (retained)
    UI->>B: Publish control {"cmd":"start"}
    B->>E: Teruskan perintah start (State -> SETTLING)
    UI->>B: Publish control {"cmd":"calibrate","target":"body"}
    B->>Body: Mulai kalibrasi baseline 5 detik
    B->>E: Tahan penilaian selama kalibrasi (State -> CALIBRATING)

    loop Setiap jendela 2 detik
        Desk->>B: Publish edge/desk/telemetry (QoS 1)
        Body->>B: Publish edge/body/telemetry (QoS 1)
        B->>E: Teruskan telemetry desk & body
        E->>E: Cek gangguan desk, ukur sudut anchor, perbarui state & skor
        E->>B: Publish session (retained)
        B->>UI: Tampilkan metrik terbaru
    end

    Note over E: Durasi diam melewati ambang L2 (45 menit skala)
    E->>B: Publish reminders {"event":"reminder","level":2,...}
    B->>Body: Aktifkan getar pendek (termux-vibrate)
    B->>Desk: Tampilkan notifikasi (termux-notification)

    Note over Body: Pengguna berganti posisi (sudut ke anchor >= 15 deg, meja tenang)
    Body->>B: Publish edge/body/telemetry
    B->>E: Deteksi Verdict.REPOSITION
    E->>B: Publish reminders {"event":"cleared","level":2,...}
    B->>Body: Hentikan getaran aktif
    B->>Desk: Hapus notifikasi pengingat
```

---

## 3. Diagram State Machine Sesi

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> SETTLING : cmd=start
    SETTLING --> CALIBRATING : cmd=calibrate(body)
    CALIBRATING --> SETTLING : kalibrasi 5 dtk selesai
    SETTLING --> ACTIVE : 60 dtk selesai (noise floor ditetapkan)
    ACTIVE --> STILL : diam >= 5 menit skala
    STILL --> STILL_LONG : diam >= 30 menit skala (L1)
    STILL_LONG --> STILL_VERY_LONG : diam >= 45 menit skala (L2)
    STILL_VERY_LONG --> STILL_CRITICAL : diam >= 60 menit skala (L3)
    ACTIVE --> LEAN_DRIFT : tilt >= 25 deg selama >= 5 menit skala
    STILL --> LEAN_DRIFT : tilt >= 25 deg selama >= 5 menit skala
    STILL --> DISTURBED : desk accel_dev_rms >= 0.6 (selisih <= 5 dtk)
    STILL_LONG --> ACTIVE : reposition (auto-clear)
    STILL_VERY_LONG --> ACTIVE : reposition (auto-clear)
    STILL_CRITICAL --> ACTIVE : reposition (auto-clear)
    STILL --> ON_BREAK : cmd=pause
    ON_BREAK --> ACTIVE : cmd=resume
    STILL --> NO_DATA : celah pesan body > 6 detik
    NO_DATA --> ACTIVE : pesan body masuk kembali
    ACTIVE --> ENDED : cmd=end
```

---

## 4. Tabel Topic MQTT (`geser/<PROJECT_ID>/...`)

| Topic | Arah | QoS | Retained | Fungsi |
|---|---|---|---|---|
| `edge/body/telemetry` | Edge `body` -> Engine, Dashboard | 1 | Tidak | Mengirim fitur hasil Processing 1 per jendela 2 detik dari saku baju. |
| `edge/desk/telemetry` | Edge `desk` -> Engine, Dashboard | 1 | Tidak | Mengirim fitur getaran dan kemiringan referensi meja per 2 detik. |
| `edge/body/presence` | Edge `body` -> Semua | 1 | Ya | Status `online` atau `offline` (dikirim otomatis oleh broker lewat *Last Will*). |
| `edge/desk/presence` | Edge `desk` -> Semua | 1 | Ya | Status `online` atau `offline` (dikirim otomatis oleh broker lewat *Last Will*). |
| `session` | Engine -> Semua | 1 | Ya | Status state machine, timer diam nyata & skala, skor, dan status node. |
| `reminders` | Engine -> Edge, Dashboard | 1 | Tidak | Pemicu pengingat (`reminder` L1..L3) dan pembatalan otomatis (`cleared`). |
| `events` | Engine -> Dashboard | 1 | Tidak | Catatan transisi status, kalibrasi, reposisi, dan perubahan kontrol. |
| `control` | Dashboard / CLI -> Engine, Edge | 1 | Tidak | Perintah kendali dua arah (`start`, `end`, `pause`, `resume`, `snooze`, `calibrate`, `time_scale`). |

---

## 5. Spesifikasi Payload JSON (Skema v1)

### A. Telemetry (`edge/<role>/telemetry`)
Hanya mengirim fitur per jendela 2 detik, bukan data mentah:
```json
{
  "v": 1,
  "device": "body",
  "run": "6af9e0c9",
  "n_msg": 42,
  "t_ms": 1790000000000,
  "window_s": 2.0,
  "samples": 20,
  "gravity": [0.02, -0.11, 0.99],
  "tilt_deg": 12.4,
  "tilt_step_deg": 1.1,
  "accel_dev_rms": 0.18,
  "gyro_path_rad": 0.05,
  "calibrated": true
}
```
**Aturan Validasi Ketat (`messaging/codec.py`):**
- Semua kunci wajib ada dan tidak boleh ada kunci tambahan.
- Nilai angka harus `finite`, vektor `gravity` harus ternormalisasi ($\|\mathbf{g}\| \approx 1.0 \pm 0.05$).
- Field `device` harus cocok dengan nama peran pada topic.
- `tilt_deg` bernilai angka hanya ketika `calibrated == true` (dan `null` bila `false`).
- Ditolak bila `|now_ms - t_ms| > 30000` ms (30 detik) atau `n_msg` tidak naik pada `run` yang sama (`SequenceGuard`).

### B. Session (`session`, Retained)
```json
{
  "v": 1,
  "state": "STILL_LONG",
  "reason": "Posisi sama melewati ambang level 1.",
  "active": true,
  "paused": false,
  "time_scale": 30.0,
  "still_real_s": 62.0,
  "still_scaled_s": 1860.0,
  "anchor_tilt_deg": 4.2,
  "reminder_level": 1,
  "last_reposition_ms": null,
  "score": 97,
  "nodes_online": {"body": true, "desk": true},
  "at_ms": 1790000062000,
  "reminders_count": 1,
  "repositions": 0,
  "longest_still_s": 1860.0,
  "lean_scaled_s": 0.0
}
```

### C. Reminders (`reminders`)
```json
{
  "event": "reminder",
  "level": 2,
  "message": "Sudah 45 menit tanpa ganti posisi. Berdiri dan regangkan badan sebentar.",
  "still_min": 45.0,
  "issued_ms": 1790000090000
}
```

### D. Control (`control`)
Hanya menerima perintah dalam *whitelist*:
- `{"cmd": "start"}`, `{"cmd": "end"}`, `{"cmd": "pause"}`, `{"cmd": "resume"}`
- `{"cmd": "snooze", "minutes": 5}` (pilihan: 5 atau 10)
- `{"cmd": "calibrate", "target": "body"}`
- `{"cmd": "time_scale", "value": 30.0}`
