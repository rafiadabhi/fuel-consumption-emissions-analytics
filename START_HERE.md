# Mulai dari Sini

Paket ini memang masih **mentah**: tidak berisi data mentah, hasil olahan, model,
atau screenshot hasil dashboard. PNG di `dashboard/mockups/` hanya referensi desain
yang sudah disetujui.

Urutannya:

1. Ekstrak ZIP dan buka folder project di terminal.
2. Buat virtual environment lalu jalankan `pip install -r requirements.txt`.
3. Salin `.env.example` menjadi `.env`, lalu isi koneksi MySQL.
4. Taruh dataset di `data/raw/MY1995-2023-Fuel-Consumption-Ratings.csv`.
5. Jalankan `python run_pipeline.py` sampai status validasi `PASS`.
6. Jalankan `streamlit run dashboard/app.py`.
7. Simpan screenshot empat halaman dashboard ke `dashboard/screenshots/`.
8. Review hasil, lalu commit ke GitHub.

Detail lengkap ada di [`README.md`](README.md).
