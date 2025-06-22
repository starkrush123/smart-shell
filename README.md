# Smart Shell v1.8

Ini adalah sebuah _shell_ atau _command prompt_ pintar yang ditenagai oleh AI dari Google (Gemini 1.5 Flash). Tujuannya sederhana: biar bisa kasih perintah ke komputer pakai bahasa sehari-hari, bukan pakai perintah teknis yang kadang susah dihafal.

## Fitur Utama

-   **Kontrol Pakai Bahasa Biasa**: Bisa minta tolong AI untuk melakukan banyak hal, mulai dari yang simpel sampai yang rumit.
-   **Manajemen File & Folder**: Buat, salin, pindah, ganti nama, baca, tulis, sampai hapus file atau folder.
-   **Manajemen Aplikasi**: Buka aplikasi yang sudah ter-install, cari aplikasi baru di repository Winget, sampai meng-install-nya langsung.
-   **Informasi Sistem**: Cek status RAM, CPU, daftar proses yang jalan, power plan, dan info sistem lainnya.
-   **Kontrol Sistem (Windows)**: Bisa minta restart, shutdown, kunci Windows, sampai membatalkan jadwal shutdown.
-   **Integrasi Khusus (Windows)**:
    -   Bisa "ngobrol" lewat screen reader NVDA.
    -   Otomatis minta hak akses Administrator untuk tugas-tugas penting.
    -   Bisa mengubah Windows Registry dan menjalankan perintah DISM (dengan konfirmasi).
-   **Fitur Tambahan**:
    -   Auto-translate teks yang di-copy ke clipboard.
    -   Unduh file dari internet atau ambil screenshot layar.
    -   Antarmuka multi-bahasa yang bisa diubah-ubah.

## Kebutuhan Sistem

-   **Sistem Operasi**: Dibuat untuk Windows, tapi beberapa fitur dasar mungkin bisa jalan di OS lain.
-   **Python**: Versi 3.8 atau yang lebih baru.
-   **Library Python**: Beberapa paket tambahan yang perlu di-install.

## Cara Setup & Instalasi

1.  **Clone Repositori**: Buka Git Bash atau terminal, lalu jalankan perintah di bawah ini untuk mengunduh semua file proyek dari GitHub.
    ```bash
    git clone [https://github.com/starkrush123/Smart-shell.git](https://github.com/starkrush123/Smart-shell.git)
    ```
    Setelah selesai, masuk ke dalam folder proyek yang baru saja dibuat:
    ```bash
    cd Smart-shell
    ```

2.  **Install Library**: Setelah masuk ke folder proyek, jalankan perintah ini untuk meng-install semua library yang dibutuhkan:
    ```bash
    pip install pyperclip pywin32 colorama google-generativeai psutil Pillow
    ```

3.  **API Key**: Buka file `config.py` pakai teks editor. Cari baris `GOOGLE_AI_API_KEY` dan ganti nilainya dengan API Key dari Google AI Studio punya sendiri.

## Cara Pakai

1.  Buka Command Prompt atau Terminal di folder proyek.
2.  Jalankan script dengan perintah:
    ```bash
    python main.py
    ```
3.  Saat pertama kali dijalankan, akan ada halaman persetujuan. Ini penting karena script ini bisa melakukan perubahan besar di sistem. Baca baik-baik, dan ketik `y` jika setuju untuk melanjutkan.
4.  Setelah itu, script akan otomatis mencoba berjalan sebagai Administrator (khusus Windows).
5.  Kalau semua sudah siap, tinggal ketik perintah apa saja pakai bahasa biasa.

    **Contoh Perintah:**
    -   `status sistem`
    -   `buka notepad`
    -   `ada file apa aja di folder Downloads?`
    -   `tolong bacain isi file catatan.txt`
    -   `restart komputer dalam 5 menit`

## ⚠️ Peringatan Penting

Harap gunakan script ini dengan sangat hati-hati. Dengan kemampuannya untuk menghapus file, mengubah registry, dan menjalankan perintah sistem, penggunaan yang salah **dapat menyebabkan kerusakan sistem atau kehilangan data**. Pengembang tidak bertanggung jawab atas masalah apa pun yang timbul dari penggunaan script ini. **Gunakan dengan risiko ditanggung sendiri.**
