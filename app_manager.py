import os
import winreg
import subprocess
import json
import threading
from colorama import Style
from config import COLOR_ERROR, COLOR_INFO, COLOR_SUCCESS, COLOR_WARNING
from language import LanguageManager

class AppManager:
    def __init__(self, lang_manager: LanguageManager):
        self.lang = lang_manager
        self.installed_apps = {}
        self.winget_available = self._check_winget()
        print(self.lang.get('appman_scanning'))
        scan_thread = threading.Thread(target=self._scan_apps, daemon=True)
        scan_thread.start()

    def _check_winget(self):
        try:
            result = subprocess.run(['winget', '--version'], capture_output=True, text=True, shell=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def _scan_registry_key(self, root_key, key_path):
        try:
            with winreg.OpenKey(root_key, key_path) as key:
                for i in range(1024):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            try:
                                display_name = str(winreg.QueryValueEx(subkey, "DisplayName")[0])
                                display_icon_path = str(winreg.QueryValueEx(subkey, "DisplayIcon")[0])
                                exe_path = display_icon_path.split(',')[0].replace('"', '').strip()
                                if display_name and os.path.exists(exe_path) and exe_path.endswith('.exe'):
                                    self.installed_apps[display_name.lower()] = {'type': 'win32', 'path': exe_path, 'name': display_name}
                            except FileNotFoundError:
                                continue
                    except OSError:
                        break
        except FileNotFoundError:
            pass

    def _scan_uwp_apps(self):
        try:
            cmd = 'powershell "Get-AppxPackage | Where-Object {$_.IsFramework -eq $false -and $_.NonRemovable -eq $false} | Select-Object Name, PackageFamilyName | ConvertTo-Json"'
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, startupinfo=si, encoding='utf-8')
            if result.returncode == 0 and result.stdout:
                uwp_apps = json.loads(result.stdout)
                if isinstance(uwp_apps, dict): uwp_apps = [uwp_apps]
                for app_info in uwp_apps:
                    name = app_info.get('Name')
                    pfn = app_info.get('PackageFamilyName')
                    if name and pfn:
                        self.installed_apps[name.lower()] = {'type': 'uwp', 'id': f"{pfn}!App", 'name': name}
        except Exception:
            pass

    def _scan_apps(self):
        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
        ]
        for root, path in registry_paths:
            self._scan_registry_key(root, path)
        self._scan_uwp_apps()
        print(self.lang.get('appman_scan_complete', count=len(self.installed_apps)))

    def _execute_launch(self, app_info):
        try:
            if app_info['type'] == 'win32':
                os.startfile(app_info['path'])
            elif app_info['type'] == 'uwp':
                os.system(f"explorer.exe shell:appsfolder\\{app_info['id']}")
            return f"Berhasil mengirim perintah untuk membuka aplikasi {app_info['name']}."
        except Exception as e:
            err_msg = self.lang.get('appman_launch_fail', name=app_info['name'], e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def launch_app(self, app_name):
        app_name_lower = app_name.lower().strip()
        if app_name_lower in self.installed_apps:
            return self._execute_launch(self.installed_apps[app_name_lower])
        
        matches = {key: info for key, info in self.installed_apps.items() if app_name_lower in key}
        if matches:
            best_match_key = min(matches.keys(), key=len)
            return self._execute_launch(matches[best_match_key])
        
        try:
            os.system(f'start {app_name_lower}')
            return self.lang.get('appman_fallback_success', name=app_name)
        except Exception as e:
            err_msg = self.lang.get('appman_fallback_fail', name=app_name, e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def winget_search(self, query):
        if not self.winget_available:
            err_msg = self.lang.get('winget_unavailable')
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
        
        try:
            command = ['winget', 'search', query, '--source', 'winget', '--accept-source-agreements']
            result = subprocess.run(command, capture_output=True, text=True, shell=True, encoding='utf-8', errors='replace')

            if result.returncode != 0:
                raise Exception(result.stderr)

            lines = result.stdout.strip().split('\n')
            if len(lines) <= 2:
                return self.lang.get('winget_no_results', query=query)

            packages = []
            header_line = lines[0]
            id_col_end = header_line.find('Id') + 2
            version_col_end = header_line.find('Version') + 7
            
            for line in lines[2:]:
                if not line.strip(): continue
                name = line[:id_col_end].strip()
                id_val = line[id_col_end:version_col_end].strip()
                if name and id_val:
                    packages.append({'name': name, 'id': id_val})
            
            if not packages:
                return self.lang.get('winget_no_results', query=query)

            header = self.lang.get('winget_search_results_header', count=len(packages))
            output_lines = [header]
            for pkg in packages:
                output_lines.append(f" Nama: {pkg['name']}\n   Id  : {pkg['id']}")
            footer = self.lang.get('winget_search_footer', count=len(packages))
            output_lines.append(footer)
            return "\n".join(output_lines)

        except Exception as e:
            err_msg = self.lang.get('winget_cli_error', e=e)
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg

    def winget_install(self, package_id):
        if not self.winget_available:
            err_msg = self.lang.get('winget_unavailable')
            print(f"{COLOR_ERROR}{err_msg}")
            return err_msg
            
        konfirmasi = input(self.lang.get('winget_install_confirm', package_id=package_id)).lower()
        if konfirmasi != 'y':
            return self.lang.get('winget_install_cancelled')
        
        print(f"{COLOR_INFO}{self.lang.get('winget_installing', package_id=package_id)}")
        try:
            command = [
                'winget', 'install', '--id', package_id, 
                '--accept-package-agreements', '--accept-source-agreements'
            ]
            subprocess.run(command, check=True, shell=True)
            return self.lang.get('winget_install_success', package_id=package_id)
        except Exception as e:
            err_msg = self.lang.get('winget_install_fail', e=e)
            print(err_msg)
            return err_msg


