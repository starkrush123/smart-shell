import os
import sys
import time
import json
import urllib.request
import threading
import inspect
import re
import webbrowser
import platform
import ctypes
import subprocess
import winreg
import shutil
import psutil
from PIL import ImageGrab
from colorama import Fore, Style
import google.generativeai as genai
import google.generativeai.protos as glm
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from config import *
from language import LanguageManager
from utils import Translator, NVDA_Handler, Clipboard_Monitor, is_admin
from app_manager import AppManager

class AI_Shell:
    def __init__(self, lang_manager, initial_config=None):
        self.script_path = os.path.abspath(__file__)
        self.lang = lang_manager
        
        if initial_config:
            self.config = initial_config
        else:
            self._load_config()
        
        self.start_time = time.time()
        self.pid = os.getpid()
        self.translator = Translator(self.lang)
        self.nvda = NVDA_Handler(self.lang)
        self.monitoring_enabled = False
        self.app_manager = AppManager(self.lang)
        self.clipboard_monitor = Clipboard_Monitor(self)
        self.session_restored = self._load_state_after_elevation()
        self.ai_model, self.chat_session = self._initialize_ai_session()
        self.lang.shell = self
        self.tools = self._get_tool_list()

    def _load_config(self):
        if os.path.exists(CONFIG_FILENAME):
            try:
                with open(CONFIG_FILENAME, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self.config = {'last_language': 'id'}
        else:
            self.config = {'last_language': 'id'}
        
        if 'last_language' not in self.config:
            self.config['last_language'] = 'id'
        self._save_config()

    def _save_config(self):
        with open(CONFIG_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4)

    def _get_tool_list(self):
        return [
            self.speak, self.pause, self.resume, self.mute, self.unmute, self.status, self.change_language, self.help, self.clear_cache, self.exit, self.restart_program,
            self.buka_website, self.buka_app, self.buka_file, self.buka_pengaturan,
            self.daftar_file, self.direktori_sekarang, self.ganti_direktori, self.buat_folder, self.baca_file, self.tulis_file, self.copy_file, self.move_file, self.rename_file, self.delete_file,
            self.daftar_aplikasi, self.cari_aplikasi, self.install_aplikasi,
            self.info_sistem, self.info_sistem_lengkap, self.info_powerplan, self.ganti_powerplan, self.dapatkan_konteks_os,
            self.kunci_windows, self.shutdown_sistem, self.batal_shutdown,
            self.daftar_proses, self.hentikan_proses, self.cari_program_hang,
            self.jalankan_perintah, self.unduh_file, self.ambil_screenshot, self.pecah_file,
            self.elevate_to_admin, self.run_dism, self.set_registry_value
        ]

    def _save_state_for_elevation(self):
        print(self.lang.get('state_saving', filename=os.path.basename(STATE_FILENAME)))
        history_for_json = []
        if not self.chat_session: return
        for content in self.chat_session.history:
            parts_list = []
            for part in content.parts:
                if hasattr(part, 'text'):
                    parts_list.append(part.text)
            if parts_list:
                history_for_json.append({'role': content.role, 'parts': parts_list})
        state_data = {
            'chat_history': history_for_json,
            'monitoring_enabled': self.monitoring_enabled,
            'is_muted': self.nvda.is_muted,
            'target_language': self.translator.target_language,
            'display_language': self.lang.current_lang_code
        }
        with open(STATE_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, indent=4)
        self.translator._save_cache()

    def _load_state_after_elevation(self):
        if os.path.exists(STATE_FILENAME):
            print(self.lang.get('state_found'))
            with open(STATE_FILENAME, 'r', encoding='utf-8') as f:
                try:
                    state_data = json.load(f)
                    self.restored_state = state_data
                    os.remove(STATE_FILENAME)
                    return True
                except Exception as e:
                    print(self.lang.get('state_load_fail', e=e))
                    self.restored_state = None
                    return False
        self.restored_state = None
        return False

    def _initialize_ai_session(self):
        if not GOOGLE_AI_API_KEY or "PASTE_API_KEY" in GOOGLE_AI_API_KEY:
            print(f"{COLOR_ERROR}{self.lang.get('ai_key_missing')}")
            return None, None
        try:
            genai.configure(api_key=GOOGLE_AI_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash-latest', tools=self._get_tool_list())
            system_prompt = """Lo adalah asisten OS yang cerdas. Misi utama lo adalah memahami maksud user dan mengeksekusi perintah menggunakan 'alat' (fungsi Python) yang tersedia seefisien mungkin.

IKUTI ATURAN INI SECARA KETAT:
1.  **ANALISIS & RENCANAKAN:** Pahami apa yang user mau. Jika permintaan user butuh beberapa langkah (misal: "pindah ke folder X, lalu baca file Y"), panggil semua alat yang diperlukan secara berurutan dalam satu giliran. JANGAN memanggil satu alat, berhenti, lalu menunggu user ngomong lagi.
2.  **MANFAATKAN KONTEKS:** Jika lo baru saja menjalankan alat seperti `dapatkan_konteks_os` atau `daftar_file`, HASIL DARI ALAT ITU ADALAH KONTEKS BARU LO. Gunakan informasi itu untuk menjawab pertanyaan user selanjutnya. JANGAN memanggil alat yang sama berulang-ulang jika informasinya sudah ada.
3.  **RANTAI LOGIKA:** Jika user bertanya, "apa isi file config.json itu?", logika lo harusnya:
    a. "Apakah gue tau `config.json` ada di sini?"
    b. (Jika tidak yakin) Panggil `dapatkan_konteks_os` atau `daftar_file` SEKALI.
    c. (Setelah melihat outputnya) "Oh, `config.json` ada. Oke, alat selanjutnya yang harus gue panggil adalah `baca_file` dengan argumen 'config.json'."
    d. JANGAN bertanya balik ke user "di mana file itu?" jika lo bisa mencarinya sendiri.
4.  **PERINTAH UMUM:** Jika perintah user terlihat seperti perintah command-line (misalnya `pip`, `git`, `npm`, `dir`, `ls`, `echo`) dan tidak ada alat lain yang lebih spesifik, GUNAKAN alat `jalankan_perintah` untuk mengeksekusinya. Ini adalah senjata pamungkas lo.
5.  **JANGAN BERTELE-TELE:** Jangan pernah bilang "Oke, saya akan menjalankan..." atau "Saya akan memanggil alat...". LAKUKAN SAJA. Langsung panggil alatnya.
6.  **JAWABAN TEKS:** Lo HANYA boleh menjawab dengan teks biasa jika:
    a. User mengajak ngobrol santai atau bertanya sesuatu yang tidak berhubungan dengan alat.
    b. Lo butuh konfirmasi untuk perintah yang sangat berbahaya (misalnya `delete_file`).
    c. Sama sekali tidak ada alat yang cocok.
    d. Setelah SEMUA alat berhasil dijalankan dan lo siap memberikan rangkuman akhirnya.
7.  **GAYA BAHASA:** Selalu gunakan 'lo-gue', santai, dan to the point.
"""
            
            chat_history = []
            if self.session_restored and self.restored_state:
                print(self.lang.get('state_restoring_history'))
                chat_history = self.restored_state['chat_history']
                self.monitoring_enabled = self.restored_state['monitoring_enabled']
                self.nvda.is_muted = self.restored_state['is_muted']
                self.translator.target_language = self.restored_state['target_language']
                self.lang.load_language(self.restored_state.get('display_language', 'id'))
            else:
                chat_history = [{'role': 'user', 'parts': [system_prompt]}, {'role': 'model', 'parts': ["Oke, gue siap."]}]

            initial_lang_name = SUPPORTED_LANGUAGES.get(self.lang.current_lang_code, 'Indonesian')
            initial_lang_prompt = f"System Notification: The session is starting. Your conversational responses must be in {initial_lang_name} to match the user's interface language, unless the user asks for something in another language."
            chat_history.append({'role': 'user', 'parts': [initial_lang_prompt]})
            chat_history.append({'role': 'model', 'parts': [f"OK, I will respond in {initial_lang_name}."]})

            chat_session = model.start_chat(history=chat_history)
            return model, chat_session
        except Exception as e:
            print(f"{COLOR_ERROR}{self.lang.get('ai_init_fail', e=e)}")
            return None, None

    def dapatkan_konteks_os(self):
        try:
            cwd = os.getcwd()
            files = os.listdir(cwd)
            os_info = f"{platform.system()} {platform.release()}"
            user_info = os.getlogin()
            admin_status = self.lang.get('status_privileges_admin') if is_admin() else self.lang.get('status_privileges_standard')

            report_lines = [
                self.lang.get('os_context_header'),
                self.lang.get('os_context_cwd', cwd=cwd),
                self.lang.get('os_context_system', os=os_info),
                self.lang.get('os_context_user', user=user_info),
                self.lang.get('os_context_admin', status=admin_status),
                self.lang.get('os_context_files_header')
            ]
            for item in files:
                report_lines.append(self.lang.get('os_context_file_item', item=item))
            
            report = "\n".join(report_lines)
            return report
        except Exception as e:
            return f"Gagal mendapatkan konteks OS: {e}"

    def speak(self, text_to_speak:str):
        translated = self.translator.translate(text_to_speak, is_manual=True)
        if translated:
            return self.nvda.speak(translated)
        return self.lang.get('speak_translation_fail')

    def pause(self):
        self.monitoring_enabled = False
        return self.lang.get('monitor_paused')

    def resume(self):
        self.monitoring_enabled = True
        return self.lang.get('monitor_resumed')

    def mute(self):
        self.nvda.is_muted = True
        return self.lang.get('mute_on')

    def unmute(self):
        self.nvda.is_muted = False
        self.nvda.pipe_found = True
        return self.lang.get('mute_off')

    def status(self):
        status_admin = self.lang.get('status_privileges_admin') if is_admin() else self.lang.get('status_privileges_standard')
        uptime_seconds = time.time() - self.start_time
        gm_time = time.gmtime(uptime_seconds)
        uptime_str = self.lang.get('time_uptime_format', h=gm_time.tm_hour, m=gm_time.tm_min, s=gm_time.tm_sec)
        
        try:
            process = psutil.Process(self.pid)
            mem_usage_mb = process.memory_info().rss / (1024 * 1024)
            mem_report = f"{mem_usage_mb:.2f} MB"
        except Exception:
            mem_report = "N/A"
        
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        status_mon = self.lang.get('status_autotranslate_on') if self.monitoring_enabled else self.lang.get('status_autotranslate_off')
        status_mute = self.lang.get('status_mute_mode_on') if self.nvda.is_muted else self.lang.get('status_mute_mode_off')
        status_nvda = self.lang.get('status_nvda_conn_ok') if self.nvda.pipe_found else self.lang.get('status_nvda_conn_fail')
        status_winget = self.lang.get('status_winget_feat_ok') if self.app_manager.winget_available else self.lang.get('status_winget_feat_no')
        stats = self.translator.session_stats
        num_apps_found = len(self.app_manager.installed_apps)
        model_name = self.ai_model.model_name.split('/')[-1] if self.ai_model else "N/A"
        history_len = len(self.chat_session.history) if self.chat_session else "N/A"
        
        cache_size_kb = 0
        if os.path.exists(CACHE_FILENAME): cache_size_kb = os.path.getsize(CACHE_FILENAME) / 1024
        cache_report = f"{len(self.translator.cache)} entri ({cache_size_kb:.2f} KB)"
        
        report = (
            f"\n{self.lang.get('status_report_header', version=SCRIPT_VERSION)}\n"
            f"{self.lang.get('status_privileges_label')}{status_admin}\n"
            f"{self.lang.get('status_os_label')}{platform.system()} {platform.release()}\n"
            f"{self.lang.get('status_python_label', version=python_version)}\n"
            f"{self.lang.get('status_ram_label', ram=mem_report)}\n"
            f"{self.lang.get('status_uptime_label')}{uptime_str}\n"
            f"{self.lang.get('status_cwd_label', cwd=os.getcwd())}\n"
            f"\n{self.lang.get('status_features_header')}\n"
            f"{self.lang.get('status_autotranslate_label')}{status_mon}\n"
            f"{self.lang.get('status_mute_mode_label')}{status_mute}\n"
            f"{self.lang.get('status_nvda_conn_label')}{status_nvda}\n"
            f"{self.lang.get('status_winget_feat_label')}{status_winget}\n"
            f"{self.lang.get('status_detected_apps_label', count=num_apps_found)}\n"
            f"\n{self.lang.get('status_session_header')}\n"
            f"{self.lang.get('status_ai_model_label', model=model_name)}\n"
            f"{self.lang.get('status_target_lang_label', lang=self.lang.current_lang_code.upper())}\n"
            f"{self.lang.get('status_history_label', count=history_len)}\n"
            f"{self.lang.get('status_cache_label', report=cache_report)}\n"
            f"{self.lang.get('status_stats_label', api=stats['api'], cache=stats['cache'])}"
        )
        print(report)
        return report

    def change_language(self, language_code:str):
        language_code = language_code.lower()
        if language_code in SUPPORTED_LANGUAGES:
            if self.lang.load_language(language_code):
                self.translator.target_language = language_code
                self.config['last_language'] = language_code
                self._save_config()
                lang_name = SUPPORTED_LANGUAGES[language_code]
                msg = self.lang.get('lang_changed', lang_code=language_code.upper(), lang_name=lang_name)
                try:
                    self.chat_session.send_message(f"System Notification: User has switched the interface language to {lang_name}. From now on, your conversational responses must also be in {lang_name}.")
                except Exception: pass
                print(f"{COLOR_SUCCESS}{msg}")
                return msg
            else:
                return f"Gagal ganti bahasa ke {language_code}."
        else:
            supported_keys = ", ".join(list(SUPPORTED_LANGUAGES.keys()))
            msg = self.lang.get('lang_invalid', code=language_code, choices=supported_keys)
            print(f"{COLOR_ERROR}{msg}")
            return msg


    def help(self):
        output = []
        output.append(f"{self.lang.get('help_header')}")
        output.append(self.lang.get('help_subtitle'))
        
        kategori = {
            self.lang.get('help_cat_system'): ["status", "exit", "restart_program", "elevate_to_admin", "info_sistem", "info_sistem_lengkap", "dapatkan_konteks_os"],
            self.lang.get('help_cat_files'): ["daftar_file", "direktori_sekarang", "ganti_direktori", "buat_folder", "baca_file", "tulis_file", "copy_file", "move_file", "rename_file", "delete_file", "pecah_file"],
            self.lang.get('help_cat_apps'): ["buka_app", "daftar_aplikasi", "cari_aplikasi", "install_aplikasi", "buka_website", "unduh_file"],
            self.lang.get('help_cat_power'): ["info_powerplan", "ganti_powerplan", "shutdown_sistem", "batal_shutdown", "kunci_windows", "daftar_proses", "hentikan_proses", "cari_program_hang"],
            self.lang.get('help_cat_other'): ["speak", "pause", "resume", "mute", "unmute", "clear_cache", "change_language", "ambil_screenshot", "jalankan_perintah", "run_dism", "set_registry_value"]
        }
        
        all_tools_map = {func.__name__: func for func in self.tools}
        
        for cat_name, tool_names in kategori.items():
            output.append(f"{COLOR_HEADER}--- {cat_name} ---")
            for tool_name in tool_names:
                if tool_name in all_tools_map:
                    tool_func = all_tools_map[tool_name]
                    desc_key = f"help_desc_{tool_name}"
                    description = self.lang.get(desc_key)
                    args = inspect.signature(tool_func)
                    param_names = [f"<{name}>" for name, param in args.parameters.items() if name != 'self']
                    output.append(f"  {COLOR_PROMPT}{tool_name} {' '.join(param_names)}{Style.RESET_ALL}")
                    output.append(f"    {description}")
            output.append("")
        
        final_output = "\n".join(output)
        print(final_output)
        return self.lang.get('help_displayed')

    def clear_cache(self):
        return self.translator.clear_cache()

    def exit(self):
        print(self.lang.get('exit_message'))
        sys.exit(0)

    def restart_program(self):
        konfirmasi = input(self.lang.get('restart_confirm')).lower()
        if konfirmasi != 'y':
            return self.lang.get('restart_cancelled')
        
        try:
            self._save_config()
            restart_args = [sys.executable, self.script_path] + sys.argv[1:]
            os.execv(sys.executable, restart_args)
        except Exception as e:
            err_msg = self.lang.get('restart_fail', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def buka_website(self, url: str):
        try:
            if not (url.startswith('http://') or url.startswith('https://')): url = 'http://' + url
            webbrowser.open(url)
            return self.lang.get('web_open_success', url=url)
        except Exception as e:
            err_msg = self.lang.get('web_open_fail', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def buka_app(self, app_name: str):
        return self.app_manager.launch_app(app_name)

    def buka_file(self, file_path: str):
        try:
            path = os.path.abspath(os.path.expanduser(file_path))
            os.startfile(path)
            return self.lang.get('file_open_success', path=path)
        except FileNotFoundError:
            err_msg = self.lang.get('file_not_found', path=file_path)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        except Exception as e:
            err_msg = self.lang.get('file_open_fail', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def direktori_sekarang(self):
        return os.getcwd()

    def ganti_direktori(self, tujuan: str):
        try:
            target_path = os.path.abspath(os.path.expanduser(tujuan))
            os.chdir(target_path)
            return self.lang.get('cd_success', cwd=os.getcwd())
        except FileNotFoundError:
            err_msg = self.lang.get('cd_fail_not_found', dest=tujuan)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        except Exception as e:
            err_msg = self.lang.get('cd_fail_generic', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def daftar_file(self, direktori: str = "."):
        try:
            path = os.path.abspath(os.path.expanduser(direktori))
            header = self.lang.get('ls_header', path=path)
            files = os.listdir(path)
            report = f"{header}\n" + "\n".join(files)
            return report
        except FileNotFoundError:
            err_msg = self.lang.get('ls_fail_not_found', path=direktori)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        except Exception as e:
            err_msg = self.lang.get('ls_fail_generic', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def info_sistem(self):
        report = f"""{self.lang.get('sysinfo_header')}
{self.lang.get('sysinfo_user', user=os.getlogin())}
{self.lang.get('sysinfo_os', os_name=platform.system(), os_release=platform.release())}"""
        return report

    def info_sistem_lengkap(self):
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            report = f"""{self.lang.get('sysinfo_full_header')}
{self.lang.get('sysinfo_cpu', usage=cpu_usage)}
{self.lang.get('sysinfo_ram_total', total=ram.total / (1024**3))}
{self.lang.get('sysinfo_ram_used', used=ram.used / (1024**3), percent=ram.percent)}
{self.lang.get('sysinfo_disk_total', total=disk.total / (1024**3))}
{self.lang.get('sysinfo_disk_used', used=disk.used / (1024**3), percent=disk.percent)}"""
            return report
        except Exception as e:
            err_msg = self.lang.get('sysinfo_fail', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def kunci_windows(self):
        time.sleep(1)
        ctypes.windll.user32.LockWorkStation()
        return self.lang.get('lock_windows_success')

    def shutdown_sistem(self, mode: str, waktu: int, unit: str):
        mode_lower = mode.lower()
        unit_lower = unit.lower()
        delay_detik = 0
        if unit_lower in ['menit', 'minute', 'minutes']: delay_detik = waktu * 60
        elif unit_lower in ['jam', 'hour', 'hours']: delay_detik = waktu * 3600
        elif unit_lower in ['detik', 'second', 'seconds']: delay_detik = waktu
        else:
            err_msg = self.lang.get('shutdown_unit_invalid', unit=unit)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        command_map = {'mati': f'shutdown /s /t {int(delay_detik)}', 'restart': f'shutdown /r /t {int(delay_detik)}', 'hibernate': 'shutdown /h', 'sleep': 'rundll32.exe powrprof.dll,SetSuspendState 0,1,0'}
        if mode_lower not in command_map:
            err_msg = self.lang.get('shutdown_mode_invalid', mode=mode)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        delay_text = f" dalam {waktu} {unit}" if mode_lower not in ['hibernate', 'sleep'] else ""
        konfirmasi = input(self.lang.get('shutdown_confirm', mode=mode_lower, delay_text=delay_text)).lower()
        if konfirmasi != 'y':
            return self.lang.get('shutdown_cancelled', mode=mode_lower)
        try:
            os.system(command_map[mode_lower])
            return self.lang.get('shutdown_success', mode=mode_lower)
        except Exception as e:
            err_msg = self.lang.get('shutdown_fail', mode=mode_lower, e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def batal_shutdown(self):
        try:
            subprocess.run(['shutdown', '/a'], check=True, capture_output=True, text=True)
            return self.lang.get('abort_shutdown_success')
        except subprocess.CalledProcessError:
            warn_msg = self.lang.get('abort_shutdown_fail_none')
            print(f"{COLOR_WARNING}{warn_msg}")
            return warn_msg
        except Exception as e:
            err_msg = self.lang.get('abort_shutdown_fail_generic', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def buka_pengaturan(self, halaman: str):
        mapping = {'bluetooth': 'bluetooth', 'display': 'display', 'tampilan': 'display', 'update': 'windowsupdate', 'akun': 'yourinfo', 'jaringan': 'network-status', 'wifi': 'network-wifi', 'power': 'powersleep', 'baterai': 'powersleep'}
        keyword = halaman.lower()
        uri = f'ms-settings:{mapping.get(keyword, keyword)}'
        os.system(f'start {uri}')
        return self.lang.get('settings_open_success', page=halaman)

    def cari_aplikasi(self, nama_aplikasi: str):
        return self.app_manager.winget_search(nama_aplikasi)

    def install_aplikasi(self, id_paket: str):
        return self.app_manager.winget_install(id_paket)

    def daftar_aplikasi(self):
        count = len(self.app_manager.installed_apps)
        header = self.lang.get('app_list_header', count=count)
        if not self.app_manager.installed_apps:
            report = f"{header}\n{self.lang.get('app_list_empty')}"
            return report
        else:
            app_names = [app_info['name'] for app_info in sorted(self.app_manager.installed_apps.values(), key=lambda x: x['name'])]
            report = f"{header}\n" + "\n".join(app_names)
            return report

    def copy_file(self, source_path: str, destination_path: str):
        try:
            src = os.path.abspath(os.path.expanduser(source_path))
            dest = os.path.abspath(os.path.expanduser(destination_path))
            shutil.copy2(src, dest)
            return self.lang.get('copy_success', filename=os.path.basename(src), dest=dest)
        except FileNotFoundError:
            err_msg = self.lang.get('copy_fail_not_found', src=source_path, dest=destination_path)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        except Exception as e:
            err_msg = self.lang.get('copy_fail_generic', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def move_file(self, source_path: str, destination_path: str):
        try:
            src = os.path.abspath(os.path.expanduser(source_path))
            dest = os.path.abspath(os.path.expanduser(destination_path))
            shutil.move(src, dest)
            return self.lang.get('move_success', filename=os.path.basename(src), dest=dest)
        except FileNotFoundError:
            err_msg = self.lang.get('move_fail_not_found', src=source_path)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        except Exception as e:
            err_msg = self.lang.get('move_fail_generic', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def rename_file(self, old_path: str, new_name: str):
        try:
            old = os.path.abspath(os.path.expanduser(old_path))
            if not os.path.exists(old): raise FileNotFoundError(f"Path '{old}' tidak ada.")
            direktori = os.path.dirname(old)
            new = os.path.join(direktori, new_name)
            os.rename(old, new)
            return self.lang.get('rename_success', new=new_name)
        except FileNotFoundError:
            err_msg = self.lang.get('rename_fail_not_found', old=old_path)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        except Exception as e:
            err_msg = self.lang.get('rename_fail_generic', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def delete_file(self, path: str):
        try:
            target_path = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(target_path): raise FileNotFoundError
            konfirmasi = input(self.lang.get('delete_confirm', path=target_path)).lower()
            if konfirmasi != 'y':
                return self.lang.get('delete_cancelled')
            if os.path.isfile(target_path): os.remove(target_path)
            elif os.path.isdir(target_path): shutil.rmtree(target_path)
            return self.lang.get('delete_success', path=target_path)
        except FileNotFoundError:
            err_msg = self.lang.get('delete_fail_not_found', path=path)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        except Exception as e:
            err_msg = self.lang.get('delete_fail_generic', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def elevate_to_admin(self):
        if is_admin():
            return self.lang.get('elevate_already_admin')
        self._save_state_for_elevation()
        try:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, self.script_path, None, 1)
            sys.exit(0)
        except Exception as e:
            err_msg = self.lang.get('elevate_fail', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            if os.path.exists(STATE_FILENAME): os.remove(STATE_FILENAME)
            return err_msg

    def run_dism(self, command: str):
        allowed_commands = ["scanhealth", "checkhealth", "restorehealth"]
        cmd_lower = command.lower()
        if cmd_lower not in allowed_commands:
            err_msg = self.lang.get('dism_invalid_command', cmd=command)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        if not is_admin():
            warn_msg = self.lang.get('dism_needs_admin')
            print(f"{COLOR_WARNING}{warn_msg}")
            return warn_msg
        full_command = f"DISM /Online /Cleanup-Image /{cmd_lower}"
        konfirmasi = input(self.lang.get('dism_confirm', full_cmd=full_command)).lower()
        if konfirmasi != 'y':
            return self.lang.get('dism_cancelled')
        try:
            print(f"{COLOR_INFO}{self.lang.get('dism_executing', full_cmd=full_command)}")
            process = subprocess.Popen(full_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None: break
                if output: print(self.lang.get('dism_output', line=output.strip()))
            if process.poll() == 0:
                return self.lang.get('dism_success', cmd=cmd_lower)
            else:
                err_msg = self.lang.get('dism_fail_code', code=process.poll())
                print(f"{COLOR_ERROR}{err_msg}")
                return err_msg
        except Exception as e:
            err_msg = self.lang.get('dism_fail_generic', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def set_registry_value(self, root_key: str, sub_key: str, value_name: str, value_data: str, value_type: str):
        if not is_admin():
            warn_msg = self.lang.get('registry_needs_admin')
            print(f"{COLOR_WARNING}{warn_msg}")
            return warn_msg
        root_map = { "hkcu": winreg.HKEY_CURRENT_USER, "hklm": winreg.HKEY_LOCAL_MACHINE }
        type_map = { "string": winreg.REG_SZ, "dword": winreg.REG_DWORD }
        root_key_lower = root_key.lower()
        value_type_lower = value_type.lower()
        if root_key_lower not in root_map:
            err_msg = self.lang.get('registry_invalid_root', key=root_key)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        if value_type_lower not in type_map:
            err_msg = self.lang.get('registry_invalid_type', type=value_type)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        reg_root = root_map[root_key_lower]
        reg_type = type_map[value_type_lower]
        try: data = int(value_data) if reg_type == winreg.REG_DWORD else str(value_data)
        except ValueError:
            err_msg = self.lang.get('registry_type_error', data=value_data, type=value_type)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        full_path = f"{root_key.upper()}\\{sub_key}"
        print(self.lang.get('registry_warning_header'))
        print(self.lang.get('registry_warning_path', path=full_path))
        print(self.lang.get('registry_warning_name', name=value_name))
        print(self.lang.get('registry_warning_data', data=data, type=value_type))
        konfirmasi = input(self.lang.get('registry_confirm')).lower()
        if konfirmasi != 'y':
            return self.lang.get('registry_cancelled')
        try:
            key = winreg.CreateKey(reg_root, sub_key)
            winreg.SetValueEx(key, value_name, 0, reg_type, data)
            winreg.CloseKey(key)
            return self.lang.get('registry_success', name=value_name, path=full_path)
        except Exception as e:
            err_msg = self.lang.get('registry_fail', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def daftar_proses(self):
        try:
            header = self.lang.get('ps_header')
            process_list = [f"{p.info['pid']} - {p.info['name']}" for p in psutil.process_iter(['pid', 'name'])]
            report = f"{header}\n" + "\n".join(process_list)
            return report
        except Exception as e:
            err_msg = self.lang.get('ps_fail', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def hentikan_proses(self, identifier: str):
        try:
            found_process = None
            if identifier.isdigit():
                pid = int(identifier)
                if psutil.pid_exists(pid): found_process = psutil.Process(pid)
            else:
                for p in psutil.process_iter(['pid', 'name']):
                    if p.info['name'].lower() == identifier.lower():
                        found_process = p
                        break
            if not found_process:
                err_msg = self.lang.get('kill_not_found', id=identifier)
                print(f"{COLOR_ERROR}{err_msg}")
                return err_msg
            
            proc_name = found_process.name()
            konfirmasi = input(self.lang.get('kill_confirm', name=proc_name, pid=found_process.pid)).lower()
            if konfirmasi != 'y':
                return self.lang.get('kill_cancelled')
            found_process.terminate()
            time.sleep(0.5)
            if found_process.is_running(): found_process.kill()
            return self.lang.get('kill_success', name=proc_name)
        except Exception as e:
            err_msg = self.lang.get('kill_fail', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def cari_program_hang(self):
        try:
            hanging_pids = set()
            def enum_windows_proc(hwnd, lParam):
                if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    result = win32gui.SendMessageTimeout(hwnd, win32con.WM_NULL, 0, 0, win32con.SMTO_ABORTIFHUNG, 1000)
                    if result == 0: hanging_pids.add(pid)
                return True
            win32gui.EnumWindows(enum_windows_proc, None)
            if not hanging_pids:
                return self.lang.get('hang_scan_safe')
            
            report_lines = [self.lang.get('hang_scan_found_header', count=len(hanging_pids))]
            for pid in hanging_pids:
                try:
                    p = psutil.Process(pid)
                    report_lines.append(self.lang.get('hang_scan_item', name=p.name(), pid=pid))
                except psutil.NoSuchProcess:
                    report_lines.append(self.lang.get('hang_scan_item_closed', pid=pid))
            report_lines.append(self.lang.get('hang_scan_footer'))
            return "\n".join(report_lines)
        except Exception as e:
            err_msg = self.lang.get('hang_scan_fail', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def jalankan_perintah(self, perintah: str):
        print(f"{COLOR_INFO}{self.lang.get('cmd_executing', cmd=perintah)}")
        full_output = []
        try:
            process = subprocess.Popen(perintah, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', cwd=os.getcwd())
            
            for line in iter(process.stdout.readline, ''):
                print(line, end='')
                full_output.append(line)
            
            process.stdout.close()
            return_code = process.wait()

            if return_code != 0:
                return f"\nPerintah selesai dengan error code: {return_code}\n{''.join(full_output)}"
            
            return ''.join(full_output)

        except Exception as e:
            err_msg = self.lang.get('cmd_fail_generic', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def unduh_file(self, url: str, nama_file_simpan: str):
        try:
            path = os.path.abspath(os.path.expanduser(nama_file_simpan))
            urllib.request.urlretrieve(url, path)
            return self.lang.get('download_success', path=path)
        except Exception as e:
            err_msg = self.lang.get('download_fail', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def baca_file(self, file_path: str):
        try:
            path = os.path.abspath(os.path.expanduser(file_path))
            with open(path, 'r', encoding='utf-8', errors='replace') as f: content = f.read()
            output = self.lang.get('read_results_header', filename=os.path.basename(path), content=content)
            return output
        except FileNotFoundError:
            err_msg = self.lang.get('read_fail_not_found', path=file_path)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        except Exception as e:
            err_msg = self.lang.get('read_fail_generic', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def tulis_file(self, file_path: str, konten: str):
        path = os.path.abspath(os.path.expanduser(file_path))
        action = self.lang.get('write_confirm_overwrite') if os.path.exists(path) else self.lang.get('write_confirm_create')
        konfirmasi = input(self.lang.get('write_confirm_prompt', action=action, path=path)).lower()
        if konfirmasi != 'y':
            return self.lang.get('write_cancelled')
        try:
            with open(path, 'w', encoding='utf-8') as f: f.write(konten)
            return self.lang.get('write_success', path=path)
        except Exception as e:
            err_msg = self.lang.get('write_fail', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def buat_folder(self, path_folder: str):
        try:
            path = os.path.abspath(os.path.expanduser(path_folder))
            os.makedirs(path, exist_ok=True)
            return self.lang.get('mkdir_success', path=path)
        except Exception as e:
            err_msg = self.lang.get('mkdir_fail', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def ambil_screenshot(self, nama_file_simpan: str = "screenshot.png"):
        try:
            path = os.path.abspath(os.path.expanduser(nama_file_simpan))
            screenshot = ImageGrab.grab()
            screenshot.save(path)
            return self.lang.get('screenshot_success', path=path)
        except Exception as e:
            err_msg = self.lang.get('screenshot_fail', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def pecah_file(self, file_sumber: str, folder_tujuan: str):
        def simpen_file_helper(full_path, content_lines, base_folder):
            folder = os.path.dirname(full_path)
            if folder and not os.path.exists(folder):
                os.makedirs(folder)
                print(self.lang.get('split_folder_created', folder=folder))
            with open(full_path, 'w', encoding='utf-8') as f: f.writelines(content_lines)
            rel_path = os.path.relpath(full_path, base_folder)
            print(self.lang.get('split_file_written', path=rel_path))

        print(self.lang.get('split_header'))
        source_file = os.path.abspath(os.path.expanduser(file_sumber))
        output_folder = os.path.abspath(os.path.expanduser(folder_tujuan))
        if not os.path.isfile(source_file):
            err_msg = self.lang.get('split_source_not_found', path=source_file)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        try:
            with open(source_file, 'r', encoding='utf-8') as f: lines = f.readlines()
        except Exception as e:
            err_msg = self.lang.get('split_read_fail', path=source_file, e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        target_path = None
        buffer = []
        total = 0
        for line in lines:
            if line.strip().startswith("##") and line.strip().endswith("##"):
                if target_path and buffer: 
                    simpen_file_helper(target_path, buffer, output_folder)
                    total += 1
                    buffer = []
                relative_path = line.strip()[2:-2].strip()
                target_path = os.path.join(output_folder, relative_path)
                print(self.lang.get('split_new_part', path=relative_path))
            else:
                if target_path: buffer.append(line)
        if target_path and buffer: 
            simpen_file_helper(target_path, buffer, output_folder)
            total += 1
        result_msg = self.lang.get('split_success', count=total, folder=output_folder)
        print(f"\n{COLOR_SUCCESS}{result_msg}")
        return result_msg

    def _get_power_plans(self):
        try:
            active_result = subprocess.run("powercfg /getactivescheme", capture_output=True, text=True, shell=True, check=True)
            active_guid_match = re.search(r'([a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12})', active_result.stdout)
            active_guid = active_guid_match.group(1) if active_guid_match else ""
            list_result = subprocess.run("powercfg /list", capture_output=True, text=True, shell=True, check=True)
            plans = []
            for line in list_result.stdout.splitlines():
                if "GUID" in line:
                    guid_match = re.search(r'([a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12})', line)
                    name_match = re.search(r'\((.*?)\)', line)
                    if guid_match and name_match:
                        guid = guid_match.group(1)
                        name = name_match.group(1)
                        plans.append({'name': name, 'guid': guid, 'active': guid == active_guid})
            return plans
        except (subprocess.CalledProcessError, FileNotFoundError): return []

    def info_powerplan(self):
        plans = self._get_power_plans()
        if not plans:
            msg = self.lang.get('powerplan_fail_fetch')
            print(f"{COLOR_ERROR}{msg}")
            return msg
        output = [self.lang.get('powerplan_header')]
        for plan in plans:
            prefix = f"{COLOR_SUCCESS} * " if plan['active'] else "   "
            output.append(self.lang.get('powerplan_item', prefix=prefix, name=plan['name'], guid=plan['guid']))
        final_report = "\n".join(output)
        return final_report

    def ganti_powerplan(self, nama_plan: str):
        if not is_admin():
            msg = self.lang.get('powerplan_change_needs_admin')
            print(f"{COLOR_ERROR}{msg}")
            return msg
        plans = self._get_power_plans()
        if not plans:
            msg = self.lang.get('powerplan_fail_fetch')
            print(f"{COLOR_ERROR}{msg}")
            return msg
        found_plan = None
        for plan in plans:
            if nama_plan.lower() in plan['name'].lower():
                found_plan = plan
                break
        if not found_plan:
            msg = self.lang.get('powerplan_fail_match', name=nama_plan)
            print(f"{COLOR_ERROR}{msg}")
            return msg
        try:
            guid = found_plan['guid']
            subprocess.run(f"powercfg /setactive {guid}", capture_output=True, text=True, shell=True, check=True)
            msg = self.lang.get('powerplan_change_success', name=found_plan['name'])
            return msg
        except subprocess.CalledProcessError as e:
            err_msg = self.lang.get('powerplan_change_fail_cmd', e=e.stderr)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        except Exception as e:
            err_msg = self.lang.get('powerplan_change_fail_generic', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def handle_clipboard_translation(self, text):
        translated_text = self.translator.translate(text)
        if translated_text: self.nvda.speak(translated_text)

    def run(self):
        self.clipboard_monitor.start()
        print(self.lang.get('shell_ready_header', version=SCRIPT_VERSION))
        admin_status = f"{COLOR_SUCCESS}{self.lang.get('status_privileges_admin')}" if is_admin() else f"{COLOR_WARNING}{self.lang.get('status_privileges_standard')}"
        print(self.lang.get('shell_privilege_status', status=admin_status))
        if self.session_restored: print(self.lang.get('shell_session_resumed'))
        
        if not all([psutil, ImageGrab]): 
            print(self.lang.get('shell_libs_warning'))
        if not self.ai_model: 
            print(self.lang.get('shell_ai_fail'))
        
        while True:
            try:
                cwd = os.getcwd()
                prompt_display = self.lang.get('prompt', blue_color=Fore.BLUE, cwd=cwd)
                command_input = input(prompt_display).strip()
                if not command_input: continue
                if not self.ai_model: 
                    print(self.lang.get('ai_not_active'))
                    continue
                
                print(f"{COLOR_INFO}{self.lang.get('thinking')}")
                response = self.chat_session.send_message(command_input)
                
                while response.candidates and response.candidates[0].content.parts and response.candidates[0].content.parts[0].function_call:
                    function_calls = response.candidates[0].content.parts
                    tool_results = []

                    for call in function_calls:
                        tool_name = call.function_call.name
                        tool_args = dict(call.function_call.args)
                        
                        if hasattr(self, tool_name):
                            tool_function = getattr(self, tool_name)
                            tool_result = tool_function(**tool_args)
                            
                            tool_results.append(glm.Part(
                                function_response=glm.FunctionResponse(
                                    name=tool_name,
                                    response={'result': tool_result}
                                ))
                            )
                        else:
                            print(self.lang.get('tool_not_found', name=tool_name))
                            tool_results.append(glm.Part(
                                function_response=glm.FunctionResponse(
                                    name=tool_name,
                                    response={'result': f"Error: Function {tool_name} not found."}
                                ))
                            )
                    
                    response = self.chat_session.send_message(tool_results)

                if response.candidates and response.candidates[0].content.parts:
                    final_text = response.text
                    if final_text:
                        final_text_cleaned = final_text.strip()
                        print(self.lang.get('ai_response', text=final_text_cleaned))
                        if any(marker in final_text_cleaned for marker in ["--- ISI DARI", "--- HASIL PERINTAH", "Oke, sekarang gue ada di:"]):
                            self.nvda.speak(final_text_cleaned)
                else: 
                    try: 
                        print(self.lang.get('ai_response_blocked', feedback=response.prompt_feedback))
                    except Exception: 
                        print(self.lang.get('ai_response_blocked_no_reason'))

            except (KeyboardInterrupt, EOFError): 
                self.exit()
            except Exception as e: 
                print(self.lang.get('unexpected_error', e=e))

