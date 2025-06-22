import os
import sys
import platform
import ctypes
import time
import json

from config import SCRIPT_DIR, CONFIG_FILENAME, SCRIPT_VERSION, COLOR_WARNING, COLOR_ERROR, Style
from language import LanguageManager
from utils import handle_first_run_consent, is_admin
from shell import AI_Shell

def _load_config_early():
    if os.path.exists(CONFIG_FILENAME):
        try:
            with open(CONFIG_FILENAME, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    return {'last_language': 'id'}

def main():
    os.chdir(SCRIPT_DIR)
    config = _load_config_early()
    lang = LanguageManager(None, config.get('last_language', 'id'))
    
    handle_first_run_consent(lang)

    if platform.system() == "Windows":
        if not is_admin():
            print(lang.get('admin_needed'))
            time.sleep(3)
            try:
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            except Exception as e:
                print(lang.get('admin_needed_failed', e=e))
                input(lang.get('exit_prompt'))
            sys.exit(0)
    
    ctypes.windll.kernel32.SetConsoleTitleW(f"Smart Shell v{SCRIPT_VERSION} [ADMIN]")
    shell = AI_Shell(lang_manager=lang, initial_config=config)
    lang.load_language(lang.current_lang_code)
    shell.run()

if __name__ == "__main__":
    main()