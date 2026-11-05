# lunar

**Konsol suara realtime offline untuk livestream — ketik satu baris, tekan Enter, langsung berbunyi.**

lunar berjalan sepenuhnya di mesinmu: satu voice neural yang selalu resident
(Kokoro-82M, 54 suara, 24 kHz) disajikan lewat konsol web lokal. Dibangun untuk
satu tugas — menjadi **suaramu di stream**: kamu ketik, penonton mendengarnya
beberapa milidetik kemudian. Tanpa cloud, tanpa akun, tanpa jaringan setelah
setup.

```
ketik → Enter → kata pertama dalam beberapa ratus milidetik (streaming per kalimat)
```

- **tinggal pakai** — `./run.sh` menyiapkan semuanya, mengunduh model sekali, membuka browser
- **100% offline** — setelah run pertama, nol panggilan jaringan; bobot model di `models/`
- **realtime** — ucapan di-stream per kalimat: kata pertama berbunyi saat sisinya masih disintesis
- **konsol live minimalis** — satu input, Enter bicara, Esc berhenti, readout latency
- **konsol config kompleks** — 54 suara, kecepatan, jeda, perilaku streaming, kamus pelafalan, varian engine, statistik
- **siap OBS** — audio keluar lewat browser; tangkap sebagai Desktop Audio

## Mulai cepat

Butuh Python 3.12+ (Ubuntu 24.04+ sudah membawanya sebagai `python3`).

```bash
git clone https://github.com/lunarjjo/lunar.git
cd lunar
./run.sh
```

Run pertama membuat venv privat, memasang dependensi ter-pin, dan mengunduh
model suara (~340 MB). Lalu konsol terbuka di `http://127.0.0.1:8765/` —
setiap start berikutnya offline dan hanya butuh beberapa detik.
Di Windows, klik dua kali `run.bat`.

Mesin tanpa internet? Unduh
[`lunar-modelpack-latest.zip`](https://github.com/lunarjjo/lunar/releases/latest)
dari halaman releases, unzip di atas repo, lalu start dengan
`LUNAR_OFFLINE=1 ./run.sh`.

## Konsol live

| tombol | aksi |
| --- | --- |
| `enter` | ucapkan barisnya (atau `ctrl+enter` jika mode diganti) |
| `esc` | hentikan ucapan seketika |
| `shift+enter` | baris baru — tempel paragraf dan tiap baris diucapkan berurutan |

Override per baris, tanpa buka menu:

```
/en Baris ini diucapkan dengan fonemizer Inggris.
/v am_adam Suara besar.
/s 1.4 Lebih cepat, ngomong lebih cepat.
```

Readout live menampilkan **latency kata pertama** tiap baris supaya kamu
selalu tahu seberapa instan suaramu.

## Menyambung ke OBS

1. Start lunar, biarkan tab konsol terbuka (di belakang pun tidak masalah).
2. Di OBS tambahkan sumber **Audio Output Capture (Desktop)** — lunar berbunyi
   lewat browser, jadi desktop audio membawanya.
3. Ingin lunar terpisah dari audio game/musik? Arahkan browser ke virtual
   audio device (mis. PulseAudio sink di Linux, VB-Cable di Windows) lalu
   tangkap device itu.
4. Opsional: tambahkan tab konsol sebagai **Browser Source** kalau ingin
   waveform terlihat di stream.

## Konsol config

`http://127.0.0.1:8765/config` — semua kenop, tersimpan live:

- **voice** — grid 41 suara yang bisa dicari (Inggris US/UK, Spanyol, Prancis,
  Hindi, Italia, Portugis) dengan tombol audisi per suara, bahasa ucapan,
  kecepatan, jeda kalimat dan klausa
- **behavior** — Enter vs Ctrl+Enter, streaming kalimat, fast first chunk,
  panjang chunk, jeda antar-chunk
- **pronunciation** — kamus live: tulis `gg`, ucapkan `gee gee`; benahi nama,
  jargon, dan kata serapan sekali untuk selamanya
- **appearance** — gelap/terang, ukuran font, readout latency, riwayat, gain utama
- **engine** — model fp32 vs int8, thread ORT, warmup, status file, unduh
  sekali-klik, statistik sesi (rata-rata ms sintesis, RTF, p50/p95 kata
  pertama), ekspor/impor/reset config

Perubahan langsung dibroadcast ke semua konsol yang terbuka — ubah kecepatan
di tengah kalimat, baris berikutnya sudah memakainya.

## Bahasa

Fonemisasi mendukung Indonesia, Inggris (US/UK), Spanyol, Prancis, Italia,
Portugis, Hindi, Jerman, Polandia. Default adalah Indonesia dengan suara
`af_heart` — ganti ke `en-us` di config atau per baris dengan `/en`.
Bobot suara Mandarin dan Jepang ada di paket tetapi butuh pipeline khusus dan
disembunyikan dari pemilih (roadmap).

## Performa

Latency kata pertama didominasi satu inferensi ONNX atas beberapa kata
pertamamu. Di CPU laptop umum, kata pertama biasanya ~100–400 ms dengan model
full precision; `tools/bench.py` mengukurnya di mesin *mu*:

```bash
python tools/bench.py            # varian saat ini
python tools/bench.py --full     # perbandingan fp32 vs int8
```

Angka dari container pengembangan (CPU lemah dan dibagi, hasilmu kemungkinan
lebih baik): p50 kata pertama ~1,0 s, RTF 0,55. Kalau int8 lebih cepat untukmu,
ganti variannya di tab engine — reload tanpa restart.

## Pengembangan

```bash
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest            # 56 test, stub engine (tanpa model)
LUNAR_LIVE=1 .venv/bin/python -m pytest   # + suite model asli setelah unduh
.venv/bin/python tools/e2e_check.py   # start server dulu; cek protokol WS penuh
.venv/bin/python tools/offline_pack.py    # bangun modelpack rilis
```

Server hanya terikat `127.0.0.1`. `LUNAR_STUB=1 python -m app` boot stub tanpa
model yang mengeluarkan dentingan lembut — berguna untuk kerja UI.

## Model & lisensi

Suara lunar adalah [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)
buatan hexgrad (Apache-2.0), dijalankan lewat ekspor
[kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) (MIT) di atas
ONNX Runtime, dengan fonemisasi espeak-ng. Atribusi lengkap di
[NOTICE.md](NOTICE.md). Kode repo ini sendiri MIT — lihat [LICENSE](LICENSE).

## Roadmap

- Pipeline Mandarin/Jepang untuk paket 54 suara penuh
- Overlay waveform streaming untuk browser source OBS
- Voice blending dan preset EQ per suara
- Echo whisper lokal opsional untuk closed captions
