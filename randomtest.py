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
import zipfile
import io
import hashlib
from packaging import version

# Sovelluksen versio ja GitHub-repo
VERSION = "0.2.0-alpha"
GITHUB_OWNER = "Linksutin"   # GitHub-käyttäjätunnuksesi
GITHUB_REPO  = "EA-FC25-Backup-Manager"  # GitHub-repon nimi

# Rekisteripolku Windowsissa
REG_PATH = r"Software\EAFC25BackupManager"

# Lokalisaatiotekstit
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
        r = requests.get(self.API_URL, timeout=10); r.raise_for_status(); return r.json()
    def is_update_available(self, latest_tag):
        latest = latest_tag.lstrip('v'); return version.parse(latest) > version.parse(self.current_version)
    def download_and_apply(self, asset_url):
        r = requests.get(asset_url, stream=True, timeout=30); r.raise_for_status(); data = r.content
        with zipfile.ZipFile(io.BytesIO(data)) as z: z.extractall(path=os.getcwd())
        os.execv(sys.executable, [sys.executable] + sys.argv)
    def check_and_update(self):
        release = self.get_latest_release()
        if self.is_update_available(release["tag_name"]):
            asset = next(a for a in release["assets"] if a["content_type"] == "application/zip"])
            self.download_and_apply(asset["browser_download_url"])
        return False

class BackupManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(translations["en"]["title"]); self.geometry("450x580"); self.resizable(False, False)
        ctk.set_appearance_mode("dark"); ctk.set_default_color_theme("blue")
        try:
            if sys.platform == "win32": self.iconbitmap(default='new_icon.ico')
        except: pass
        # rekisteri ja tilat
        self.toaster = ToastNotifier()
        self.language = self.read_registry("language") or "en"
        self.source_path = self.read_registry("source_path") or os.path.join(os.getenv('LOCALAPPDATA'), "EA SPORTS FC 25", "settings")
        self.backup_path = self.read_registry("backup_path") or os.path.expanduser("~\\Documents")
        self.auto_backup_interval = int(self.read_registry("auto_backup_interval") or 30)
        self.last_backup_time = self.read_registry("last_backup_time") or "Never"
        next_reg = self.read_registry("next_backup_time")
        self.next_backup_time = (datetime.strptime(next_reg, "%Y-%m-%d %H:%M:%S") if next_reg else datetime.now() + timedelta(minutes=self.auto_backup_interval))
        # GUI ja taustat
        self.build_ui(); self.check_update_notification(); self.after(3600000, self.check_update_notification)
        self.check_fc25_status(); self.update_countdown()
        self.bind('<Control-q>', lambda e: self.exit_app()); self.bind('<Control-b>', lambda e: self.manual_backup())

    def build_ui(self):
        ctk.CTkButton(self, text="⚙️", width=40, height=40, command=self.open_settings).place(x=400, y=10)
        self.last_backup_label = ctk.CTkLabel(self, text=f"{translations[self.language]['last_backup']}: {self.format_last_backup_time()}")
        self.last_backup_label.pack(pady=(50,5))
        self.next_backup_label = ctk.CTkLabel(self, text=f"{translations[self.language]['next_backup']}: {self.auto_backup_interval} {translations[self.language]['minutes']}")
        self.next_backup_label.pack(pady=5)
        self.create_button(translations[self.language]['manual_backup'], self.manual_backup).pack(pady=10, padx=40, fill="x")
        self.create_button(translations[self.language]['open_folder'], self.open_backup_folder).pack(pady=10, padx=40, fill="x")
        ctk.CTkLabel(self, text="─"*70, text_color="gray").pack(pady=(40,5))
        self.fc25_status_label = ctk.CTkLabel(self, text="Checking FC 25 status...", text_color="gray", font=("Arial",14))
        self.fc25_status_label.pack(pady=(40,5))
        self.version_label = ctk.CTkLabel(self, text=f"Version {VERSION}", text_color="gray", font=("Arial",14))
        self.version_label.pack(pady=(20,5))
        ctk.CTkButton(self, text="🔄 Tarkista päivitykset", command=self.tarkista_paivitykset, fg_color="#1f6aa5", hover_color="#144272").pack(pady=(5,15), padx=40, fill="x")
        ctk.CTkLabel(self, text="Code by: Linksutin | UI by: Linksu", text_color="gold", font=("Arial",18)).pack(side="bottom", pady=10)

    def format_last_backup_time(self):
        if self.last_backup_time == "Never":
            return translations[self.language]['never']
        return self.last_backup_time

    def manual_backup(self, event=None):
        now = datetime.now(); ts = now.strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(self.backup_path, f"backup_{ts}")
        try:
            shutil.copytree(self.source_path, dest)
            self.last_backup_time = now.strftime("%c")
            self.last_backup_label.configure(text=f"{translations[self.language]['last_backup']}: {self.format_last_backup_time()}")
            self.next_backup_time = datetime.now() + timedelta(minutes=self.auto_backup_interval)
            self.notify("Backup Complete", f"Backup saved at {self.last_backup_time}")
            self.write_registry("last_backup_time", self.last_backup_time)
            self.write_registry("next_backup_time", self.next_backup_time.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            self.notify("Backup Failed", str(e))

    # Muut metodit: check_update_notification, tarkista_paivitykset, update_countdown,
    # check_fc25_status, open_backup_folder, open_settings, create_button,
    # build_settings_ui jne. sekä read_registry, write_registry, notify, exit_app.

if __name__ == "__main__":
    app = BackupManagerApp(); app.mainloop()