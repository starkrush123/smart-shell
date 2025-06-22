import os
import sys
import time
import json
import threading
import ctypes
import pyperclip
import win32file
import win32clipboard
import win32con
import win32gui
import pywintypes
import urllib.request
import urllib.parse
from colorama import Style
from config import SCRIPT_VERSION, CACHE_FILENAME, COLOR_PROMPT, COLOR_HEADER, COLOR_WARNING, COLOR_SUCCESS, COLOR_ERROR, COLOR_INFO, COLOR_CMD
from language import LanguageManager

def handle_first_run_consent(lang_manager: LanguageManager):
    config_dir = os.path.join(os.path.expanduser('~'), '.smartshell')
    consent_file = os.path.join(config_dir, 'consent.flag')

    if os.path.exists(consent_file):
        return

    os.system('cls' if os.name == 'nt' else 'clear')
    print(lang_manager.get('line_separator'))
    print(lang_manager.get('welcome_message', version=SCRIPT_VERSION))
    print(lang_manager.get('line_separator') + Style.RESET_ALL + "\n")
    
    print(lang_manager.get('attention'))
    print(lang_manager.get('attention_desc_1'))
    print(lang_manager.get('attention_desc_2'))
    print(lang_manager.get('attention_desc_3'))
    
    print(f"{COLOR_HEADER}{lang_manager.get('disclaimer_header')}{Style.RESET_ALL}")
    print(f"""
1.  {lang_manager.get('disclaimer_1_title')} {lang_manager.get('disclaimer_1_desc')}

2.  {lang_manager.get('disclaimer_2_title')} {lang_manager.get('disclaimer_2_desc')}

3.  {lang_manager.get('disclaimer_3_title')} {lang_manager.get('disclaimer_3_desc')}

{lang_manager.get('disclaimer_warning')}
""")

    try:
        response = input(lang_manager.get('consent_prompt')).lower()
        if response != 'y':
            print(lang_manager.get('consent_denied'))
            sys.exit(0)
        
        os.makedirs(config_dir, exist_ok=True)
        with open(consent_file, 'w') as f:
            f.write(f"Agreed on {time.ctime()}")
        print(lang_manager.get('consent_thanks'))
        
    except (KeyboardInterrupt, EOFError):
        print(lang_manager.get('consent_input_cancelled'))
        sys.exit(0)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

class Translator:
    def __init__(self, lang_manager: LanguageManager):
        self.lang = lang_manager
        self.cache = self._load_cache()
        self.session_stats = {'api': 0, 'cache': 0}
        self.target_language = lang_manager.current_lang_code
    
    def _load_cache(self):
        if os.path.exists(CACHE_FILENAME):
            with open(CACHE_FILENAME, 'r', encoding='utf-8') as f:
                try: return json.load(f)
                except json.JSONDecodeError: return {}
        return {}

    def _save_cache(self):
        with open(CACHE_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=4, ensure_ascii=False)

    def translate(self, text, is_manual=False):
        cache_key = text.strip().lower()
        if not is_manual and cache_key in self.cache:
            self.session_stats['cache'] += 1
            return self.cache[cache_key]
        try:
            url_safe_text = urllib.parse.quote(text)
            url = f"[https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=](https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=){self.target_language}&dt=t&q={url_safe_text}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    data = json.loads(response.read())
                    translated_text = "".join([item[0] for item in data[0] if item[0]])
                    self.session_stats['api'] += 1
                    if not is_manual: 
                        self.cache[cache_key] = translated_text
                        self._save_cache()
                    return translated_text
            return None
        except Exception as e:
            print(self.lang.get('translate_error', e=e))
            return None

    def clear_cache(self):
        self.cache = {}
        self.session_stats = {'api': 0, 'cache': 0}
        self._save_cache()
        return self.lang.get('cache_cleared')

class NVDA_Handler:
    def __init__(self, lang_manager: LanguageManager):
        self.lang = lang_manager
        self.is_muted = False
        self.pipe_found = True

    def speak(self, text_to_speak):
        if self.is_muted: 
            return self.lang.get('nvda_denied_muted')
        if not self.pipe_found: 
            return self.lang.get('nvda_pipe_not_found')
        
        pipe_name = r'\\.\pipe\NVDAControlPipe'
        command = f'speak "{text_to_speak}" 0 -1'
        try:
            handle = win32file.CreateFile(pipe_name, win32file.GENERIC_WRITE, 0, None, win32file.OPEN_EXISTING, 0, None)
            win32file.WriteFile(handle, command.encode('utf-8'))
            win32file.CloseHandle(handle)
            return self.lang.get('nvda_sent_text', text=text_to_speak)
        except pywintypes.error as e:
            if e.winerror == 2:
                self.pipe_found = False
                self.is_muted = True
                err_msg = self.lang.get('nvda_failsafe')
                print(f"\n{COLOR_ERROR}{err_msg}")
                return err_msg
            else:
                err_msg = self.lang.get('nvda_connect_error', e=e)
                print(f"\n{COLOR_ERROR}{err_msg}")
                return err_msg

class Clipboard_Monitor(threading.Thread):
    def __init__(self, shell_instance):
        super().__init__(daemon=True)
        self.shell = shell_instance
        self.lang = shell_instance.lang
        self.last_clipboard = ""

    def run(self):
        self.ClipboardListenerWindow(self)

    class ClipboardListenerWindow:
        def __init__(self, parent_monitor):
            self.parent = parent_monitor
            self.lang = parent_monitor.lang
            wc = win32gui.WNDCLASS()
            wc.lpszClassName = "ClipboardListenerCompat"
            wc.lpfnWndProc = self.wnd_proc
            class_atom = win32gui.RegisterClass(wc)
            self.hwnd = win32gui.CreateWindow(class_atom, "Clipboard Listener", 0, 0, 0, 0, 0, 0, 0, 0, None)
            self.next_viewer = win32clipboard.SetClipboardViewer(self.hwnd)
            win32gui.PumpMessages()

        def wnd_proc(self, hwnd, msg, wparam, lparam):
            if msg == win32con.WM_DRAWCLIPBOARD and self.parent.shell.monitoring_enabled:
                try:
                    current_clipboard = pyperclip.paste()
                    if isinstance(current_clipboard, str) and current_clipboard and current_clipboard != self.parent.last_clipboard:
                        self.parent.last_clipboard = current_clipboard
                        print(self.lang.get('clipboard_detected'))
                        self.parent.shell.handle_clipboard_translation(current_clipboard)
                except pyperclip.PyperclipException:
                    pass
            elif msg == win32con.WM_CHANGECBCHAIN:
                if wparam == self.next_viewer:
                    self.next_viewer = lparam
                elif self.next_viewer:
                    win32gui.SendMessage(self.next_viewer, msg, wparam, lparam)
            elif msg == win32con.WM_DESTROY:
                win32clipboard.ChangeChain(self.hwnd, self.next_viewer)
                win32gui.PostQuitMessage(0)
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

