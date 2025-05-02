import customtkinter as ctk
import sys
import os
import psutil
import shutil
import tkinter.filedialog as filedialog
from datetime import datetime, timedelta
from win10toast import ToastNotifier
import winreg
import requests
from packaging import version
from PIL import Image

# Global hotkeys
try:
    import keyboard
except ImportError:
    keyboard = None

# App info
VERSION = "0.4.0-alpha"
GITHUB_OWNER = "Linksutin"
GITHUB_REPO = "EA-FC-Backup-Manager"
REG_PATH = r"Software\\EAFC25BackupManager"

# Translations
translations = {
    "en": {
        "title": "EA FC 25 Backup Manager",
        "settings": "Settings",
        "manual_backup": "Start Manual Backup",
        "open_folder": "Open Backup Folder",
        "last_backup": "Last backup",
        "next_backup": "Next backup in",
        "fc_running": "FC 25 is running",
        "fc_not_running": "FC 25 is not running",
        "settings_folder": "Change Settings Folder",
        "backup_folder": "Change Backup Folder",
        "backup_interval": "Change Backup Interval",
        "language": "Change Language",
        "never": "Never",
        "minutes": "minutes",
        "save": "Save"
    },
    "fi": {
        "title": "EA FC 25 Varmuuskopiohallinta",
        "settings": "Asetukset",
        "manual_backup": "Aloita manuaalinen varmuuskopio",
        "open_folder": "Avaa varmuuskopiokansio",
        "last_backup": "Viimeisin varmuuskopio",
        "next_backup": "Seuraava varmuuskopio",
        "fc_running": "FC 25 on käynnissä",
        "fc_not_running": "FC 25 ei ole käynnissä",
        "settings_folder": "Vaihda asetuskansio",
        "backup_folder": "Vaihda varmuuskopiokansio",
        "backup_interval": "Vaihda varmuuskopiointiväli",
        "language": "Vaihda kieli",
        "never": "Ei koskaan",
        "minutes": "minuuttia",
        "save": "Tallenna"
    }
}

class GitHubUpdater:
    API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

    def __init__(self, current_version):
        self.current_version = current_version

    def get_latest_release(self):
        response = requests.get(self.API_URL, timeout=10)
        response.raise_for_status()
        return response.json()

    def is_update_available(self, tag):
        latest = tag.lstrip('v')
        return version.parse(latest) > version.parse(self.current_version)

    def download_and_apply(self, url):
        new_exe = os.path.join(os.getcwd(), "EAFC25BackupManager_new.exe")
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        with open(new_exe, 'wb') as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        os.execv(new_exe, [new_exe] + sys.argv[1:])

    def check_and_update(self):
        data = self.get_latest_release()
        tag = data.get('tag_name', '')
        if self.is_update_available(tag):
            asset = next((a for a in data.get('assets', []) if a['name'].endswith('.exe')), None)
            if asset:
                self.download_and_apply(asset['browser_download_url'])

class BackupManagerApp(ctk.CTk):
    def __init__(self):
        # Remove leftover updater
        updater = os.path.join(os.getcwd(), 'EAFC25BackupManager_new.exe')
        if os.path.exists(updater):
            try:
                os.remove(updater)
            except:
                pass
        # Auto-update
        try:
            GitHubUpdater(VERSION).check_and_update()
        except:
            pass

        super().__init__()
        ctk.set_appearance_mode('dark')
        ctk.set_default_color_theme('blue')

        self.title(translations['en']['title'])
        self.geometry('450x580')
        self.resizable(False, False)

        # Global hotkeys
        if keyboard:
            try:
                keyboard.add_hotkey('ctrl+b', self.manual_backup)
                keyboard.add_hotkey('ctrl+q', self.exit_app)
            except:
                pass

        # Notification
        try:
            self.toaster = ToastNotifier()
        except:
            self.toaster = None

        # Load settings
        self.language = self.read_registry('language') or 'en'
        self.source_path = self.read_registry('source_path') or os.path.join(
            os.getenv('LOCALAPPDATA',''), 'EA SPORTS FC 25', 'settings'
        )
        self.backup_path = self.read_registry('backup_path') or os.path.expanduser('~\\Documents')
        self.auto_interval = int(self.read_registry('auto_backup_interval') or 30)
        self.last_time = self.read_registry('last_backup_time') or 'Never'
        next_ts = self.read_registry('next_backup_time')
        try:
            self.next_time = datetime.strptime(next_ts, '%Y-%m-%d %H:%M:%S') if next_ts else datetime.now() + timedelta(minutes=self.auto_interval)
        except:
            self.next_time = datetime.now() + timedelta(minutes=self.auto_interval)

        self.build_ui()
        self.check_fc25_status()
        self.update_countdown()

    def build_ui(self):
        # Settings button
        ctk.CTkButton(
            self, text='⚙️', width=40, height=40,
            command=self.open_settings
        ).place(x=400, y=10)

        # Logo and credits
        try:
            logo_path = os.path.join(os.path.dirname(__file__), 'logo.png')
            logo_img = Image.open(logo_path).resize((80, 80))
            self.logo_ctk_image = ctk.CTkImage(
                light_image=logo_img,
                dark_image=logo_img,
                size=(80, 80)
            )
            ctk.CTkLabel(self, image=self.logo_ctk_image, text='').pack(pady=(60, 5))
        except Exception:
            pass
        ctk.CTkLabel(
            self, text='by Linksu & mryoshl',
            font=('Arial', 14), text_color='gray'
        ).pack(pady=(0, 15))

        # Last & next backup
        self.last_lbl = ctk.CTkLabel(
            self, text=f"{translations[self.language]['last_backup']}: {self.last_time}"
        )
        self.last_lbl.pack(pady=5)
        self.next_lbl = ctk.CTkLabel(
            self, text=f"{translations[self.language]['next_backup']}: {self.auto_interval} {translations[self.language]['minutes']}"
        )
        self.next_lbl.pack(pady=5)

        # Manual backup & open folder buttons
        ctk.CTkButton(
            self, text=translations[self.language]['manual_backup'],
            command=self.manual_backup
        ).pack(pady=10, fill='x', padx=40)
        ctk.CTkButton(
            self, text=translations[self.language]['open_folder'],
            command=self.open_backup_folder
        ).pack(pady=10, fill='x', padx=40)

        # Separator & status
        ctk.CTkLabel(self, text='─' * 70, text_color='gray').pack(pady=20)
        self.status_lbl = ctk.CTkLabel(self, text='', text_color='gray')
        self.status_lbl.pack(pady=5)

        # Version label
        ctk.CTkLabel(
            self, text=f"Version {VERSION}",
            text_color='gray'
        ).pack(pady=(20, 5))

    def open_settings(self):
        settings_win = ctk.CTkToplevel(self)
        settings_win.title(translations[self.language]['settings'])
        settings_win.geometry('300x300')
        settings_win.resizable(False, False)
        ctk.CTkLabel(
            settings_win, text=translations[self.language]['settings'],
            font=('Arial', 18)
        ).pack(pady=10)
        ctk.CTkButton(
            settings_win, text=translations[self.language]['settings_folder'],
            command=self.change_settings_folder
        ).pack(fill='x', padx=20, pady=5)
        ctk.CTkButton(
            settings_win, text=translations[self.language]['backup_folder'],
            command=self.change_backup_folder
        ).pack(fill='x', padx=20, pady=5)
        ctk.CTkButton(
            settings_win, text=translations[self.language]['backup_interval'],
            command=self.change_backup_interval
        ).pack(fill='x', padx=20, pady=5)

    def change_settings_folder(self):
        new = filedialog.askdirectory(initialdir=self.source_path)
        if new:
            self.source_path = new
            self.write_registry('source_path', new)

    def change_backup_folder(self):
        new = filedialog.askdirectory(initialdir=self.backup_path)
        if new:
            self.backup_path = new
            self.write_registry('backup_path', new)

    def change_backup_interval(self):
        interval_win = ctk.CTkToplevel(self)
        interval_win.title(translations[self.language]['backup_interval'])
        interval_win.geometry('300x250')
        interval_win.resizable(False, False)
        ctk.CTkLabel(
            interval_win, text=translations[self.language]['backup_interval'],
            font=('Arial', 16)
        ).pack(pady=(20, 10))
        slider = ctk.CTkSlider(interval_win, from_=1, to=180, number_of_steps=179)
        slider.set(self.auto_interval)
        slider.pack(pady=10)
        value_lbl = ctk.CTkLabel(
            interval_win, text=f"{self.auto_interval} {translations[self.language]['minutes']}"
        )
        value_lbl.pack()