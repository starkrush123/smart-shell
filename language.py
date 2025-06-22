import os
import json
import re
import google.generativeai as genai
from colorama import Style
from config import SCRIPT_DIR, SUPPORTED_LANGUAGES, COLOR_INFO, COLOR_SUCCESS, COLOR_ERROR, COLOR_HEADER, COLOR_WARNING, COLOR_PROMPT, COLOR_CMD, COLOR_AI

class LanguageManager:
    def __init__(self, shell_instance, initial_lang_code='id'):
        self.shell = shell_instance
        self.lang_dir = os.path.join(SCRIPT_DIR, 'lang')
        self.default_lang = 'id'
        self.current_lang_code = initial_lang_code
        self.strings = {}
        os.makedirs(self.lang_dir, exist_ok=True)
        self._sync_default_lang_file()
        self.load_language(self.current_lang_code, translate_on_load=False)

    def get(self, key, **kwargs):
        template = self.strings.get(key, f"<{key}_NOT_FOUND>")
        try:
            kwargs.setdefault('reset_all', Style.RESET_ALL)
            kwargs.setdefault('header_color', COLOR_HEADER)
            kwargs.setdefault('info_color', COLOR_INFO)
            kwargs.setdefault('success_color', COLOR_SUCCESS)
            kwargs.setdefault('warning_color', COLOR_WARNING)
            kwargs.setdefault('error_color', COLOR_ERROR)
            kwargs.setdefault('prompt_color', COLOR_PROMPT)
            kwargs.setdefault('cmd_color', COLOR_CMD)
            kwargs.setdefault('ai_color', COLOR_AI)
            return template.format(**kwargs)
        except KeyError as e:
            return f"<{key}_FORMAT_ERROR: Missing {e}>"

    def load_language(self, lang_code, translate_on_load=True):
        if lang_code != self.default_lang and translate_on_load:
            self._update_target_lang_file(lang_code)

        lang_file = os.path.join(self.lang_dir, f"{lang_code}.json")
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                self.strings = json.load(f)
            self.current_lang_code = lang_code
            return True
        except (json.JSONDecodeError, FileNotFoundError):
            if os.path.exists(os.path.join(self.lang_dir, f"{self.default_lang}.json")):
                 with open(os.path.join(self.lang_dir, f"{self.default_lang}.json"), 'r', encoding='utf-8') as f:
                    self.strings = json.load(f)
            self.current_lang_code = self.default_lang
            return False

    def _update_target_lang_file(self, target_lang_code):
        default_file_path = os.path.join(self.lang_dir, f"{self.default_lang}.json")
        target_file_path = os.path.join(self.lang_dir, f"{target_lang_code}.json")

        with open(default_file_path, 'r', encoding='utf-8') as f:
            default_strings = json.load(f)

        target_strings = {}
        if os.path.exists(target_file_path):
            try:
                with open(target_file_path, 'r', encoding='utf-8') as f:
                    target_strings = json.load(f)
            except json.JSONDecodeError:
                target_strings = {}
        
        strings_to_translate = {k: v for k, v in default_strings.items() if k not in target_strings}

        if not strings_to_translate:
            return

        print(f"{COLOR_INFO}[Lang] Terdeteksi {len(strings_to_translate)} teks baru. Gue coba terjemahin ya...")
        
        translated_snippets = self._translate_snippets(strings_to_translate, target_lang_code)

        if translated_snippets:
            target_strings.update(translated_snippets)
            with open(target_file_path, 'w', encoding='utf-8') as f:
                json.dump(target_strings, f, indent=4, ensure_ascii=False)
            print(f"{COLOR_SUCCESS}[Lang] Berhasil! File '{target_lang_code}.json' udah di-update.")

    def _translate_snippets(self, snippets, target_lang_code):
        if not snippets:
            return None
        
        target_lang_name = SUPPORTED_LANGUAGES.get(target_lang_code, 'English')
        print(f"{COLOR_INFO}[AI] Minta AI nerjemahin {len(snippets)} teks ke '{target_lang_name}'...")
        try:
            if not self.shell or not self.shell.ai_model:
                print(f"{COLOR_ERROR}[AI/Lang] Model AI utama belum siap untuk nerjemahin.")
                return None

            model = self.shell.ai_model
            prompt = (
                f"You are a translation assistant. Translate the JSON values from Indonesian to {target_lang_name}. "
                "Keep the JSON keys exactly the same. Preserve any placeholders like `{variable}`. "
                "Your output MUST be a single, valid JSON object containing only the translated key-value pairs. Do not add any explanation or markdown formatting like ```json. "
                f"Here is the JSON object with the strings to translate:\n\n{json.dumps(snippets, indent=2, ensure_ascii=False)}"
            )
            
            response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.1))
            cleaned_response_text = re.sub(r'```json\n|```', '', response.text).strip()
            return json.loads(cleaned_response_text)
        except Exception as e:
            print(f"{COLOR_ERROR}[AI/Lang] Gagal pas proses nerjemahin dan nyimpen: {e}")
            return None

    def _get_master_strings(self):
        return {
            "line_separator": "===================================================================",
            "welcome_message": "  Selamat Datang di {prompt_color}Smart Shell v{version}{header_color}!",
            "attention": "{warning_color}PERHATIAN:{reset_all}",
            "attention_desc_1": "Skrip ini sekarang punya kemampuan untuk melakukan perubahan signifikan pada sistem operasi lo.",
            "attention_desc_2": "Untuk fungsionalitas penuh, skrip ini akan selalu mencoba untuk berjalan dengan {success_color}Hak Akses Administrator{reset_all}.",
            "attention_desc_3": "Saat dijalankan, UAC prompt Windows kemungkinan akan muncul untuk meminta persetujuan.\n",
            "disclaimer_header": "--- DISCLAIMER & KETENTUAN PENGGUNAAN ---",
            "disclaimer_1_title": "{prompt_color}Tanggung Jawab Pengguna:{reset_all}",
            "disclaimer_1_desc": "Lo memegang kendali dan tanggung jawab penuh atas semua \n    perintah yang diberikan kepada skrip ini, baik secara langsung maupun melalui AI.",
            "disclaimer_2_title": "{prompt_color}Risiko Penggunaan:{reset_all}",
            "disclaimer_2_desc": "Dengan kemampuannya untuk memodifikasi file, registri, dan \n    menjalankan perintah level sistem, penggunaan yang tidak hati-hati {error_color}DAPAT{reset_all} menyebabkan \n    kerusakan sistem, kehilangan data, atau celah keamanan.",
            "disclaimer_3_title": "{prompt_color}Tanpa Jaminan:{reset_all}",
            "disclaimer_3_desc": "Pengembang tidak bertanggung jawab atas segala kerusakan atau \n    kerugian yang mungkin timbul dari penggunaan skrip ini. {warning_color}Gunakan dengan risiko lo sendiri.{reset_all}",
            "disclaimer_warning": "Harap berhati-hati saat menggunakan perintah berbahaya seperti {cmd_color}delete_file{reset_all}, {cmd_color}set_registry_value{reset_all},\natau {cmd_color}jalankan_perintah{reset_all}.",
            "consent_prompt": "{info_color}Dengan mengetik 'y', lo mengerti dan setuju dengan semua poin di atas. Lanjutkan? (y/n): {reset_all}",
            "consent_denied": "\n{warning_color}Persetujuan ditolak. Program akan ditutup.{reset_all}",
            "consent_thanks": "\n{success_color}Terima kasih. Persetujuan disimpan. Menjalankan Smart Shell...{reset_all}",
            "consent_input_cancelled": "\n{warning_color}Input dibatalkan. Program akan ditutup.{reset_all}",
            "admin_needed": "\n{warning_color}Hak akses Admin dibutuhkan. Mencoba elevate otomatis...{reset_all}",
            "admin_needed_failed": "{error_color}Gagal elevate otomatis: {e}{reset_all}",
            "exit_prompt": "Tekan Enter untuk keluar...",
            "translate_error": "\n{error_color}[Error] Gagal translate: {e}",
            "cache_cleared": "[Cache] Beres! Cache dan statistik sesi dihapus.",
            "nvda_denied_muted": "Perintah ditolak: Mode hening aktif.",
            "nvda_pipe_not_found": "Perintah gagal: Koneksi ke NVDA tidak ditemukan.",
            "nvda_sent_text": "\n{success_color}[NVDA] Mengirim teks ke NVDA untuk diucapkan: {text}",
            "nvda_failsafe": "[FAIL-SAFE] Gagal konek ke NVDA. Mode hening otomatis aktif.",
            "nvda_connect_error": "[Error] Gagal konek ke NVDA: {e}",
            "appman_scanning": "{info_color}[AppManager] Memindai aplikasi ter-install...",
            "appman_scan_complete": "{success_color}[AppManager] Selesai! Ditemukan {count} aplikasi unik.",
            "appman_launching": "[AppManager] Ditemukan '{name}'. Mencoba membuka...",
            "appman_launch_fail": "[OS] Gagal membuka '{name}': {e}",
            "appman_fallback_start": "[OS] Gak nemu di daftar, mencoba via command 'start' untuk '{name}'...",
            "appman_fallback_success": "Berhasil mengirim perintah 'start' untuk '{name}'.",
            "appman_fallback_fail": "[OS] Gagal total buat buka '{name}': {e}",
            "winget_unavailable": "[Winget] Perintah 'winget' tidak ditemukan. Pastikan Winget sudah ter-install di sistem lo.",
            "winget_searching": "[Winget] Mencari '{query}' via winget CLI...",
            "winget_search_results_header": "--- HASIL PENCARIAN WINGET ({count}) ---",
            "winget_no_results": "Tidak ada hasil yang cocok ditemukan untuk '{query}'.",
            "winget_search_footer": "\nDitemukan {count} hasil. Gunakan 'install aplikasi <Id>' untuk install.",
            "winget_cli_error": "[Winget] Terjadi error saat menjalankan perintah winget: {e}",
            "winget_install_confirm": "{warning_color}[KONFIRMASI] Lo akan menginstall '{package_id}' menggunakan winget. Lanjutkan? (y/n): ",
            "winget_install_cancelled": "[Winget] Instalasi dibatalkan oleh user.",
            "winget_installing": "[Winget] Menjalankan instalasi untuk '{package_id}' via winget CLI...",
            "winget_install_success": "[Winget] Instalasi '{package_id}' berhasil dimulai. Cek notifikasi Windows untuk progresnya.",
            "winget_install_fail": "\n{error_color}[Winget] Gagal memulai instalasi. Cek lagi ID paketnya atau jalankan sebagai admin. Error: {e}",
            "clipboard_detected": "\n{info_color}[Clipboard] Teks baru terdeteksi...",
            "state_saving": "{info_color}[State] Menyimpan konteks sesi ke {filename}...",
            "state_found": "{success_color}[State] File konteks ditemukan! Memuat ulang sesi...",
            "state_load_fail": "{error_color}[State] Gagal memuat file konteks: {e}",
            "state_restoring_history": "{success_color}[State] Mengembalikan history percakapan...",
            "ai_key_missing": "[AI Error] GOOGLE_AI_API_KEY belum diisi.",
            "ai_init_fail": "[AI Error] Gagal menginisialisasi model AI: {e}",
            "speak_translation_fail": "Gagal menerjemahkan teks sebelum diucapkan.",
            "monitor_paused": "[Status] OK, monitoring clipboard udah dimatiin.",
            "monitor_resumed": "[Status] Siap! Monitoring clipboard dinyalain lagi.",
            "mute_on": "[Status] Mode Hening aktif.",
            "mute_off": "[Status] Suara diaktifkan lagi.",
            "status_report_header": "\n{header_color}--- STATUS SISTEM & SCRIPT (v{version}) ---{reset_all}",
            "status_privileges_label": "  Hak Akses        : ",
            "status_privileges_admin": "ADMIN",
            "status_privileges_standard": "STANDAR",
            "status_os_label": "  OS               : ",
            "status_python_label": "  Python           : v{version}",
            "status_ram_label": "  Penggunaan RAM   : {ram}",
            "status_uptime_label": "  Waktu Aktif      : ",
            "status_cwd_label": "  Direktori Aktif  : {cwd}",
            "status_features_header": "\n{header_color}--- KONEKTIVITAS & FITUR ---{reset_all}",
            "status_autotranslate_label": "  Auto-Translate   : ",
            "status_autotranslate_on": "{success_color}NYALA{reset_all}",
            "status_autotranslate_off": "{warning_color}MATI{reset_all}",
            "status_mute_mode_label": "  Mode Hening      : ",
            "status_mute_mode_on": "{warning_color}Aktif{reset_all}",
            "status_mute_mode_off": "Nonaktif",
            "status_nvda_conn_label": "  Koneksi NVDA     : ",
            "status_nvda_conn_ok": "{success_color}Tersambung{reset_all}",
            "status_nvda_conn_fail": "{error_color}Gagal{reset_all}",
            "status_winget_feat_label": "  Fitur Winget     : ",
            "status_winget_feat_ok": "{success_color}Tersedia (CLI){reset_all}",
            "status_winget_feat_no": "{warning_color}Tidak Tersedia{reset_all}",
            "status_detected_apps_label": "  Aplikasi Terdeteksi: {count}",
            "status_session_header": "\n{header_color}--- SESI, AI & CACHE ---{reset_all}",
            "status_ai_model_label": "  Model AI         : {model}",
            "status_target_lang_label": "  Bahasa Target    : {lang}",
            "status_history_label": "  History Sesi     : {count} item",
            "status_cache_label": "  Cache Terjemahan : {report}",
            "status_stats_label": "  Statistik Sesi   : {api} (API) | {cache} (Cache)",
            "lang_changed": "[Bahasa] Target bahasa diubah ke: {lang_code} ({lang_name})",
            "lang_invalid": "[AI] Maaf, kode bahasa '{code}' gak valid. Pilihan: {choices}",
            "help_header": "{header_color}--- DAFTAR PERINTAH SMART SHELL ---",
            "help_subtitle": "Lo bisa panggil perintah-perintah ini pake bahasa biasa.\n",
            "help_cat_system": "Sistem & Program",
            "help_cat_files": "Navigasi & File",
            "help_cat_apps": "Aplikasi & Jaringan",
            "help_cat_power": "Power & Proses",
            "help_cat_other": "Fitur Lain",
            "help_displayed": "Bantuan sudah ditampilkan.",
            "help_desc_speak": "Menerjemahkan dan mengucapkan sebuah kalimat spesifik.",
            "help_desc_pause": "Mematikan fitur auto-translate dari clipboard.",
            "help_desc_resume": "Menyalakan lagi fitur auto-translate dari clipboard.",
            "help_desc_mute": "Mematikan output suara NVDA.",
            "help_desc_unmute": "Mengaktifkan lagi output suara NVDA.",
            "help_desc_status": "(STATUS) Menampilkan status script yang detail dan informatif.",
            "help_desc_change_language": "(BAHASA) Mengganti bahasa target untuk terjemahan & interface (id, en, ja).",
            "help_desc_help": "(BANTUAN) Menampilkan daftar semua perintah yang tersedia.",
            "help_desc_clear_cache": "(CACHE) Menghapus semua cache terjemahan yang tersimpan.",
            "help_desc_exit": "(PROGRAM) Keluar dari program Smart Shell.",
            "help_desc_restart_program": "(PROGRAM) Me-restart script Smart Shell ini.",
            "help_desc_buka_website": "(WEB) Membuka sebuah alamat website di browser.",
            "help_desc_buka_app": "(APP) Membuka aplikasi yang terinstall atau via command run.",
            "help_desc_buka_file": "(FILE) Membuka sebuah file dengan aplikasi defaultnya.",
            "help_desc_buka_pengaturan": "(APP) Membuka halaman Settings Windows tertentu.",
            "help_desc_daftar_file": "(FILE) Menampilkan daftar file dan folder di sebuah direktori.",
            "help_desc_direktori_sekarang": "(FILE) Menampilkan direktori (folder) yang sedang aktif saat ini.",
            "help_desc_ganti_direktori": "(FILE) Berpindah ke direktori (folder) lain.",
            "help_desc_buat_folder": "(FILE) Membuat sebuah direktori/folder baru.",
            "help_desc_baca_file": "(FILE) Membaca isi dari sebuah file teks.",
            "help_desc_tulis_file": "(FILE) Menulis atau menimpa konten ke sebuah file teks.",
            "help_desc_copy_file": "(FILE) Menyalin sebuah file dari satu lokasi ke lokasi lain.",
            "help_desc_move_file": "(FILE) Memindahkan sebuah file atau folder dari satu lokasi ke lokasi lain.",
            "help_desc_rename_file": "(FILE) Mengganti nama sebuah file atau folder.",
            "help_desc_delete_file": "(FILE-BAHAYA) Menghapus file atau folder (PERMANEN!).",
            "help_desc_daftar_aplikasi": "(APP) Menampilkan daftar aplikasi yang berhasil terdeteksi saat startup.",
            "help_desc_cari_aplikasi": "(APP) Mencari ketersediaan aplikasi di Windows Package Manager (winget).",
            "help_desc_install_aplikasi": "(APP) Menginstall aplikasi menggunakan ID Paket dari winget. Butuh Admin.",
            "help_desc_info_sistem": "(INFO) Menampilkan informasi dasar sistem.",
            "help_desc_info_sistem_lengkap": "(INFO) Menampilkan informasi sistem yang lebih detail (CPU, RAM, Disk).",
            "help_desc_info_powerplan": "(POWER) Mengecek daftar & status power plan Windows yang aktif.",
            "help_desc_ganti_powerplan": "(POWER) Mengganti power plan aktif berdasarkan namanya. Butuh Admin.",
            "help_desc_kunci_windows": "(POWER) Mengunci sesi Windows (sama seperti Win+L).",
            "help_desc_shutdown_sistem": "(POWER-BAHAYA) Mematikan, restart, hibernate, atau sleep. Unit bisa 'detik', 'menit', atau 'jam'.",
            "help_desc_batal_shutdown": "(POWER) Membatalkan jadwal restart atau shutdown yang sedang berjalan.",
            "help_desc_daftar_proses": "(PROSES) Menampilkan daftar semua proses yang sedang berjalan.",
            "help_desc_hentikan_proses": "(PROSES-BAHAYA) Menghentikan paksa sebuah proses berdasarkan PID atau nama prosesnya.",
            "help_desc_cari_program_hang": "(PROSES) Mendeteksi dan menampilkan daftar program/aplikasi yang 'Not Responding' (hang).",
            "help_desc_jalankan_perintah": "(CMD) Menjalankan perintah command line (CMD/PowerShell) secara langsung.",
            "help_desc_unduh_file": "(WEB) Mengunduh file dari sebuah URL dan menyimpannya ke disk.",
            "help_desc_ambil_screenshot": "(GAMBAR) Mengambil screenshot layar penuh dan menyimpannya ke file.",
            "help_desc_pecah_file": "(FILE) Memecah file besar jadi modular pake penanda '## path/file.py ##'.",
            "help_desc_elevate_to_admin": "(ADMIN) Meminta hak akses admin dengan me-restart script (jika belum admin).",
            "help_desc_run_dism": "(ADMIN) Menjalankan perintah DISM yang aman (ScanHealth, CheckHealth, RestoreHealth).",
            "help_desc_set_registry_value": "(ADMIN-BAHAYA) Mengubah value di Windows Registry.",
            "help_desc_dapatkan_konteks_os": "(INFO) Mengambil dan menampilkan konteks OS saat ini (direktori, file, dll).",
            "exit_message": "\n{ai_color}Smart Shell: Oke, gue cabut dulu ya. Kalo butuh lagi, panggil aja!",
            "restart_confirm": "{warning_color}[KONFIRMASI] Lo yakin mau restart program ini? (y/n): ",
            "restart_cancelled": "[Program] Restart dibatalin.",
            "restarting": "{info_color}[Program] Oke, gue restart sekarang...",
            "restart_fail": "Gagal restart: {e}",
            "web_opening": "[OS] Buka {url}...",
            "web_open_success": "Berhasil mengirim perintah untuk membuka website {url}",
            "web_open_fail": "[OS] Gagal buka website: {e}",
            "file_opening": "[OS] Buka file: {path}...",
            "file_open_success": "Berhasil mengirim perintah untuk membuka file {path}",
            "file_not_found": "[OS] File gak ketemu: {path}",
            "file_open_fail": "[OS] Gagal buka file: {e}",
            "cwd_is": "[PWD] Direktori sekarang: {cwd}",
            "cd_success": "Oke, sekarang gue ada di: {cwd}",
            "cd_fail_not_found": "Gagal pindah, direktori '{dest}' gak ketemu.",
            "cd_fail_generic": "Gagal pindah direktori: {e}",
            "ls_header": "--- ISI DARI: {path} ---",
            "ls_fail_not_found": "[OS] Direktori gak ketemu: {path}",
            "ls_fail_generic": "[OS] Gagal baca direktori: {e}",
            "sysinfo_header": "--- INFO SISTEM ---",
            "sysinfo_user": "- Username: {user}",
            "sysinfo_os": "- OS      : {os_name} {os_release}",
            "sysinfo_full_header": "--- INFO SISTEM LENGKAP ---",
            "sysinfo_cpu": "- CPU Usage : {usage}%",
            "sysinfo_ram_total": "- RAM Total : {total:.2f} GB",
            "sysinfo_ram_used": "- RAM Used  : {used:.2f} GB ({percent}%)",
            "sysinfo_disk_total": "- Disk Total: {total:.2f} GB",
            "sysinfo_disk_used": "- Disk Used : {used:.2f} GB ({percent}%)",
            "sysinfo_fail": "[OS] Gagal dapet info sistem lengkap: {e}",
            "lock_windows_msg": "[OS] Oke, Windows gue kunci ya. Sampai jumpa lagi!",
            "lock_windows_success": "Berhasil mengirim perintah untuk mengunci Windows.",
            "shutdown_unit_invalid": "[OS] Unit waktu '{unit}' gak dikenal. Coba 'detik', 'menit', atau 'jam'.",
            "shutdown_mode_invalid": "[OS] Mode '{mode}' gak valid. Coba: mati, restart, hibernate, sleep.",
            "shutdown_confirm": "{warning_color}[KONFIRMASI] Lo YAKIN mau {mode} komputer{delay_text}? (y/n): ",
            "shutdown_cancelled": "[OS] Oke, perintah {mode} dibatalin.",
            "shutdown_executing": "[OS] Menjalankan perintah {mode}...",
            "shutdown_success": "Berhasil mengirim perintah untuk {mode} komputer.",
            "shutdown_fail": "Gagal menjalankan perintah {mode}: {e}",
            "abort_shutdown_success": "[OS] Oke, jadwal restart/shutdown berhasil dibatalin.",
            "abort_shutdown_fail_none": "[OS] Gagal: Kayaknya gak ada jadwal restart/shutdown yg aktif untuk dibatalkan.",
            "abort_shutdown_fail_generic": "[OS] Gagal total pas batalin shutdown: {e}",
            "settings_opening": "[OS] Buka pengaturan '{page}'...",
            "settings_open_success": "Berhasil mengirim perintah untuk membuka pengaturan {page}.",
            "app_list_header": "--- DAFTAR APLIKASI TERDETEKSI ({count}) ---",
            "app_list_empty": "Tidak ada aplikasi yang terdeteksi.",
            "copy_executing": "[OS] Menyalin dari '{src}' ke '{dest}'...",
            "copy_success": "File '{filename}' berhasil disalin ke '{dest}'.",
            "copy_fail_not_found": "Gagal salin: Salah satu path tidak ditemukan ({src} atau {dest}).",
            "copy_fail_generic": "Gagal menyalin file: {e}",
            "move_executing": "[OS] Memindahkan dari '{src}' ke '{dest}'...",
            "move_success": "File atau folder '{filename}' berhasil dipindahkan ke '{dest}'.",
            "move_fail_not_found": "Gagal pindah: File atau folder sumber tidak ditemukan ({src}).",
            "move_fail_generic": "Gagal memindahkan: {e}",
            "rename_executing": "Mengganti nama '{old}' menjadi '{new}'...",
            "rename_success": "Berhasil ganti nama ke '{new}'.",
            "rename_fail_not_found": "Gagal ganti nama: File atau folder '{old}' tidak ditemukan.",
            "rename_fail_generic": "Gagal ganti nama: {e}",
            "delete_confirm": "{warning_color}[KONFIRMASI] YAKIN mau hapus '{path}'? Ini gak bisa di-undo! (y/n): ",
            "delete_cancelled": "[OS] Penghapusan dibatalkan oleh user.",
            "delete_executing": "[OS] Menghapus '{path}'...",
            "delete_success": "Berhasil menghapus '{path}'.",
            "delete_fail_not_found": "Gagal hapus: File atau folder '{path}' tidak ditemukan.",
            "delete_fail_generic": "Gagal menghapus: {e}",
            "elevate_already_admin": "Gue udah jalan di mode Admin kok.",
            "elevate_restarting": "[System] Oke, gue coba restart dengan hak akses admin ya...",
            "elevate_fail": "Gagal elevate ke mode admin: {e}",
            "dism_invalid_command": "[DISM] Perintah '{cmd}' gak diizinin. Cuma bisa: ScanHealth, CheckHealth, RestoreHealth.",
            "dism_needs_admin": "[DISM] Perintah ini butuh hak akses admin. Coba 'elevate' dulu.",
            "dism_confirm": "{warning_color}[KONFIRMASI] Lo mau jalanin '{full_cmd}'? Ini bisa makan waktu lama. (y/n): ",
            "dism_cancelled": "[DISM] Operasi dibatalkan oleh user.",
            "dism_executing": "[DISM] Menjalankan {full_cmd}... Sabar ya.",
            "dism_output": "{cmd_color}[Output] {line}",
            "dism_success": "\n[DISM] Perintah '{cmd}' selesai dengan sukses.",
            "dism_fail_code": "\n[DISM] Perintah selesai dengan error. Kode: {code}",
            "dism_fail_generic": "[DISM] Gagal total pas jalanin DISM: {e}",
            "registry_needs_admin": "[Registry] Edit registri butuh hak akses admin. Coba 'elevate' dulu.",
            "registry_invalid_root": "[Registry] Root key '{key}' gak valid. Cuma bisa HKCU atau HKLM.",
            "registry_invalid_type": "[Registry] Value type '{type}' gak valid. Cuma bisa 'string' atau 'dword'.",
            "registry_type_error": "[Registry] Gagal konversi '{data}' ke tipe {type}.",
            "registry_warning_header": "{warning_color}--- PERINGATAN KERAS ---",
            "registry_warning_path": "Lo akan mengubah registri di path: {cmd_color}{path}",
            "registry_warning_name": "  - Value Name : {cmd_color}{name}",
            "registry_warning_data": "  - Value Data : {cmd_color}{data} ({type})",
            "registry_confirm": "{warning_color}YAKIN BANGET mau lanjut? Salah-salah Windows bisa rusak! (y/n): ",
            "registry_cancelled": "[Registry] Operasi dibatalkan oleh user. Keputusan bijak.",
            "registry_writing": "[Registry] Mencoba menulis ke registri...",
            "registry_success": "[Registry] Berhasil! Value '{name}' di '{path}' telah diatur.",
            "registry_fail": "[Registry] GAGAL TOTAL! Error: {e}",
            "ps_header": "--- DAFTAR PROSES BERJALAN (PID - Nama) ---",
            "ps_fail": "[OS] Gagal dapet daftar proses: {e}",
            "kill_not_found": "[OS] Gagal, proses dengan '{id}' gak ketemu.",
            "kill_confirm": "{warning_color}[KONFIRMASI] Lo YAKIN mau matiin proses '{name}' (PID: {pid})? (y/n): ",
            "kill_cancelled": "[OS] Oke, perintah dibatalin.",
            "kill_success": "[OS] Berhasil menghentikan proses '{name}'.",
            "kill_fail": "[OS] Gagal menghentikan proses: {e}",
            "hang_scan_executing": "[OS] Memindai program yang nge-hang. Tunggu sebentar...",
            "hang_scan_safe": "[OS] Aman! Gak ada program yang terdeteksi hang.",
            "hang_scan_found_header": "{warning_color}--- DITEMUKAN {count} PROGRAM HANG ---",
            "hang_scan_item": "  - {name} (PID: {pid})",
            "hang_scan_item_closed": "  - Proses dengan PID: {pid} (sudah ditutup)",
            "hang_scan_footer": "\n{info_color}Gunakan 'hentikan_proses <nama/PID>' untuk mematikan paksa program di atas.",
            "hang_scan_fail": "[OS] Gagal saat mencari program hang: {e}",
            "cmd_executing": "[CMD] Menjalankan: '{cmd}'...",
            "cmd_results_header": "--- HASIL PERINTAH '{cmd}' ---",
            "cmd_output_header": "Output:\n{output}\n",
            "cmd_error_header": "Error:\n{error}\n",
            "cmd_return_code": "Return Code: {code}",
            "cmd_fail_generic": "[CMD] Gagal total pas jalanin perintah: {e}",
            "download_executing": "[Net] Mengunduh dari '{url}' ke '{path}'...",
            "download_success": "Berhasil mengunduh dan menyimpan file sebagai '{path}'.",
            "download_fail": "Gagal mengunduh file: {e}",
            "read_executing": "[OS] Membaca file: {path}...",
            "read_results_header": "--- ISI FILE: {filename} ---\n{content}",
            "read_fail_not_found": "[OS] File gak ketemu: {path}",
            "read_fail_generic": "[OS] Gagal baca file: {e}",
            "write_confirm_overwrite": " menimpa ",
            "write_confirm_create": " membuat ",
            "write_confirm_prompt": "{warning_color}[KONFIRMASI] Lo YAKIN mau{action}file '{path}'? (y/n): ",
            "write_cancelled": "[OS] Oke, perintah menulis file dibatalin.",
            "write_executing": "[OS] Menulis ke file: {path}...",
            "write_success": "Berhasil menulis ke file '{path}'.",
            "write_fail": "Gagal menulis ke file: {e}",
            "mkdir_executing": "[OS] Membuat folder: {path}...",
            "mkdir_success": "Berhasil membuat atau memastikan folder '{path}' ada.",
            "mkdir_fail": "Gagal membuat folder: {e}",
            "screenshot_executing": "[OS] Mengambil screenshot...",
            "screenshot_success": "Screenshot berhasil disimpan di '{path}'.",
            "screenshot_fail": "Gagal mengambil screenshot: {e}",
            "split_header": "{header_color}--- PEMISAH FILE MODULAR ---",
            "split_source_not_found": "File sumber '{path}' gak ketemu!",
            "split_read_fail": "Gagal baca file sumber '{path}': {e}",
            "split_folder_created": "{info_color}[Splitter] Folder dibuat: {folder}",
            "split_file_written": "{success_color}[Splitter] File ditulis: {path}",
            "split_new_part": "{info_color}[Splitter] Ketemu bagian baru: {path}",
            "split_success": "Selesai! Total file yang dibuat: {count} di folder '{folder}'.",
            "powerplan_fail_fetch": "[Power] Gagal mendapatkan daftar power plan.",
            "powerplan_header": "{header_color}--- POWER PLAN WINDOWS ---",
            "powerplan_item": "{prefix}{name} ({info_color}{guid}{reset_all})",
            "powerplan_change_needs_admin": "[Power] Gagal, ganti power plan butuh hak akses Admin. Coba 'elevate' dulu.",
            "powerplan_fail_match": "[Power] Gak nemu power plan yang namanya mirip '{name}'.",
            "powerplan_change_success": "Berhasil ganti power plan ke '{name}'",
            "powerplan_change_fail_cmd": "[Power] Gagal ganti power plan. Cek lagi GUID-nya. Error: {e}",
            "powerplan_change_fail_generic": "[Power] Gagal total pas ganti power plan: {e}",
            "time_uptime_format": "{h} jam {m} menit {s} detik",
            "cwd_home_fail": "{warning_color}Gagal pindah ke home directory, tetap di direktori script.",
            "shell_ready_header": "\n{header_color}===== Smart Shell (v{version}) =====",
            "shell_privilege_status": "{info_color}Status Hak Akses: {status}",
            "shell_session_resumed": "{success_color}Berhasil di-elevate! Melanjutkan sesi sebelumnya.",
            "shell_libs_warning": "{warning_color}[Peringatan] Gagal import 'psutil' atau 'Pillow'. Beberapa fitur OS gak akan jalan. (pip install psutil Pillow)",
            "shell_ai_fail": "{error_color}Gagal memulai AI. Fungsionalitas terbatas.",
            "prompt": "\n{reset_all}{blue_color}{cwd}{reset_all}{prompt_color}\n> ",
            "ai_not_active": "{error_color}[AI Error] Fitur AI tidak aktif.",
            "thinking": "[AI] Berpikir...",
            "tool_not_found": "{warning_color}[AI Error] AI mencoba memanggil fungsi '{name}' yang tidak ada.",
            "ai_response": "{ai_color}Smart Shell: {text}",
            "ai_response_blocked": "\n{warning_color}[AI] Respons dari AI kosong atau diblokir. Alasan: {feedback}",
            "ai_response_blocked_no_reason": "\n{warning_color}[AI] Respons dari AI kosong atau diblokir.",
            "unexpected_error": "{error_color}Terjadi error tak terduga: {e}",
            "os_context_header": "--- Konteks Sistem Operasi Saat Ini ---",
            "os_context_cwd": "  Direktori Aktif: {cwd}",
            "os_context_files_header": "  Isi Direktori:",
            "os_context_file_item": "    - {item}",
            "os_context_system": "  Sistem Operasi : {os}",
            "os_context_user": "  User Aktif     : {user}",
            "os_context_admin": "  Status Hak     : {status}"
        }

    def _sync_default_lang_file(self):
        master_strings = self._get_master_strings()
        default_file_path = os.path.join(self.lang_dir, f"{self.default_lang}.json")

        disk_strings = {}
        if os.path.exists(default_file_path):
            try:
                with open(default_file_path, 'r', encoding='utf-8') as f:
                    disk_strings = json.load(f)
            except json.JSONDecodeError:
                pass 

        new_keys = {k: v for k, v in master_strings.items() if k not in disk_strings}

        if new_keys:
            print(f"[Lang] Sinkronisasi template bahasa, ditemukan {len(new_keys)} item baru...")
            disk_strings.update(new_keys)
            try:
                with open(default_file_path, 'w', encoding='utf-8') as f:
                    json.dump(disk_strings, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"[Lang] Gagal update file 'id.json': {e}")

