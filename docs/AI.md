# Versi AI GESER (Revisi Tugas)

Revisi dosen: sistem diterapkan dalam bentuk **AI yang menghasilkan Input -> Output**.
GESER versi AI memakai **supervised learning** (materi *AI for Everyone*: "A to B mapping"):
AI belajar dari tabel data yang berisi Input (A) dan Output (B), bukan dari ambang yang kita tulis tangan.

| Materi dosen | Penerapan di GESER |
|---|---|
| ANI (AI yang mengerjakan satu hal) | AI khusus satu tugas: mengenali kondisi duduk dari 2 HP |
| Supervised learning: Input (A) -> Output (B) | A = 6 fitur sensor, B = 1 dari 4 kondisi duduk |
| Data = tabel (dataset) | `data/posture_dataset.csv` (6000 baris) |
| Data itu *messy* (label salah, nilai hilang) | 3% label salah dan ~2% nilai hilang sengaja dimasukkan |
| Training / validation / test | 60% / 20% / 20% (`tools/ml_train.py`) |
| Acceptance criteria (mis. 95%) | Akurasi test >= 95% (`--target`) |
| Jangan berharap 100% | Batas atas ~97% karena 3% label salah |
| Deep learning / neural network | MLP 2 lapisan tersembunyi (16 dan 8 neuron) |
| Edge deployment | Bobot diekspor ke JSON 6,6 KB, inferensi Python murni (tanpa scikit-learn) |

## Input (A) dan Output (B)

**Input (A)**, dihitung per jendela 2 detik oleh `features.py` yang sudah ada:

| Fitur | Sumber | Arti |
|---|---|---|
| `body_tilt_deg` | HP body | sudut kemiringan dari posisi acuan |
| `body_tilt_step_deg` | HP body | perubahan sudut dari jendela sebelumnya |
| `body_accel_dev_rms` | HP body | getaran di luar gravitasi |
| `body_gyro_path_rad` | HP body | total putaran giroskop |
| `desk_accel_dev_rms` | HP desk | getaran meja |
| `desk_gyro_path_rad` | HP desk | putaran HP meja |

**Output (B)**, satu label per jendela beserta tingkat keyakinan:

| Label | Arti |
|---|---|
| `TEGAK` | duduk tegak, posisi baik |
| `CONDONG` | badan condong dari posisi acuan |
| `BERGERAK` | sedang bergerak / ganti posisi |
| `MEJA_TERGANGGU` | meja terguncang, bukan gerakan tubuh |

Contoh: `A = [31.2, 0.2, 0.1, 0.05, 0.05, 0.03]  ->  B = CONDONG (97%)`.

## Hasil (data simulasi, seed 42)

| Model | Akurasi validation | Akurasi test |
|---|---|---|
| Aturan lama (ambang tetap `default.yaml`) | 88,8% | 87,7% |
| Decision Tree | 95,3% | 94,7% |
| **Neural Network (MLP)** | **95,8%** | **95,5%** |

Kriteria 95% terpenuhi pada data uji (1200 baris). Confusion matrix dan kurva belajar ada di `reports/`.

> **Penting (jujur soal data):** dataset bawaan dibangkitkan oleh simulasi fisika sensor
> (`src/geser/ml/synthetic.py`) yang memakai *pipeline fitur asli GESER*. Angka di atas
> membuktikan alur AI-nya bekerja, **bukan** akurasi pada HP dan tubuh sungguhan.
> Untuk laporan akhir, rekam data nyata (bagian di bawah) lalu latih ulang.

## Cara menjalankan

```bash
pip install -e ".[dashboard,dev,ml]"

python tools/ml_make_dataset.py          # 1. buat dataset  -> data/posture_dataset.csv
python tools/ml_train.py                 # 2. latih + evaluasi -> models/posture_mlp.json, reports/
python tools/ml_demo.py                  # 3. demo Input (A) -> Output (B), tanpa HP
python tools/ml_live.py                  # 4. AI waktu nyata dari 2 HP (setelah geser-edge jalan)
pytest tests/unit/test_ml.py             # 5. tes
```

## Mengumpulkan data nyata dari HP (disarankan)

```bash
geser-edge --role body      # HP di saku dada
geser-edge --role desk      # HP di meja
# Rekam 2 menit per kondisi, sambil benar-benar melakukan kondisi tsb:
python tools/record_telemetry.py --out recordings/tegak.csv --duration 120
python tools/ml_label_recording.py --in recordings/tegak.csv --label TEGAK --out data/real_tegak.csv
# ulangi untuk CONDONG, BERGERAK, MEJA_TERGANGGU, lalu:
python tools/ml_make_dataset.py --per-class 0 --extra data/real_tegak.csv --extra data/real_condong.csv \
    --extra data/real_bergerak.csv --extra data/real_meja.csv --out data/posture_real.csv
python tools/ml_train.py --data data/posture_real.csv
```

Lakukan **kalibrasi** (tombol Kalibrasi 5 dtk) sebelum merekam, karena baris tanpa
`body_tilt_deg` dilewati oleh `ml_label_recording.py`.

## Struktur kode baru

```
src/geser/ml/schema.py     definisi fitur (A) dan label (B)
src/geser/ml/synthetic.py  pembuat dataset simulasi (memakai features.py asli)
src/geser/ml/model.py      inferensi Python murni dari model JSON
src/geser/ml/live.py       pasangkan body+desk, prediksi, haluskan, hitung lama condong
tools/ml_make_dataset.py   dataset CSV
tools/ml_train.py          training, validasi, test, ekspor, grafik
tools/ml_demo.py           demo offline
tools/ml_live.py           AI waktu nyata via MQTT (hanya subscribe)
tools/ml_label_recording.py rekaman HP -> data berlabel
models/posture_mlp.json    model terlatih
```

Engine rule-based yang lama tetap utuh. AI berjalan berdampingan sebagai pengamat (`ml_live.py`)
sehingga demo lama tidak rusak.

## Keterbatasan
- Dataset bawaan simulasi; akurasi nyata bergantung data yang direkam.
- Model dilatih untuk satu posisi HP (saku dada) dan perlu kalibrasi per sesi.
- Sistem hanya memperkirakan dari gerakan HP, bukan alat medis.
