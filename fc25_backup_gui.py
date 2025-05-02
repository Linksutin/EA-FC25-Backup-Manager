import customtkinter as ctk
import sys
import os
import psutil
import shutil
import tkinter.filedialog as filedialog
from datetime import datetime, timedelta
import winreg
import requests
from packaging import version
from win10toast import ToastNotifier
from PIL import Image
from customtkinter import CTkImage
import locale

VERSION = "0.4.0-alpha"
GITHUB_OWNER = "Linksutin"
GITHUB_REPO = "EA-FC-Backup-Manager"
REG_PATH = r"Software\\EAFC25BackupManager"

translations = {
    "en": {
        "title": "EA FC Backup Manager",
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
        "save": "Save",
        "keep_backups": "Number of backups to keep",
        "version": "Version",
        "credits": "Code by: mryoshl | UI by: Linksu",
        "at": "at"
    },
    "fi": {
        "title": "EA FC 25 Varmuuskopiohallinta",
        "settings": "Asetukset",
        "manual_backup": "Aloita manuaalinen varmuuskopio",
        "open_folder": "Avaa varmuuskopiokansio",
        "last_backup": "Viimeisin varmuuskopio",
        "next_backup": "Seuraava varmuuskopio otetaan",
        "fc_running": "FC 25 on käynnissä",
        "fc_not_running": "FC 25 ei ole käynnissä",
        "settings_folder": "Vaihda asetuskansio",
        "backup_folder": "Vaihda varmuuskopiokansio",
        "backup_interval": "Vaihda varmuuskopiointiväli",
        "language": "Vaihda kieli",
        "never": "Ei koskaan",
        "minutes": "minuutin päästä",
        "save": "Tallenna",
        "keep_backups": "Säilytettävien varmuuskopioiden määrä",
        "version": "Versio",
        "credits": "Koodi: mryoshl | Käyttöliittymä: Linksu",
        "at": "klo"
    }
}

class GitHubUpdater:
    API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

    def __init__(self, current_version):
        self.current_version = current_version

    def get_latest_release(self):
        r = requests.get(self.API_URL, timeout=10)
        r.raise_for_status()
        return r.json()

    def is_update_available(self, latest_tag):
        return version.parse(latest_tag.lstrip('v')) > version.parse(self.current_version)

    def download_and_apply(self, asset_url):
        exe_name = "EA FC BackupManager.exe"
        exe_path = os.path.join(os.getcwd(), exe_name)
        # Remove old exe
        if os.path.exists(exe_path):
            os.remove(exe_path)
        # Download new exe
        r = requests.get(asset_url, stream=True, timeout=30)
        r.raise_for_status()
        with open(exe_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        # Exec new
        os.execv(exe_path, [exe_path] + sys.argv[1:])

    def check_and_update(self):
        rel = self.get_latest_release()
        tag = rel.get("tag_name", "").lstrip('v')
        if self.is_update_available(tag):
            asset = next((a for a in rel.get("assets", []) if a.get("name", "").endswith(".exe")), None)
            if asset:
                self.download_and_apply(asset["browser_download_url"])

class BackupManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        try:
            GitHubUpdater(VERSION).check_and_update()
        except:
            pass

        self.toaster = ToastNotifier()
        try:
            import keyboard
            keyboard.add_hotkey('ctrl+b', self.manual_backup)
            keyboard.add_hotkey('ctrl+q', self.exit_app)
        except:
            pass

        # Load settings
        self.language = self.read_registry("language") or "en"
        self.source_path = self.read_registry("source_path") or os.path.join(
            os.getenv('LOCALAPPDATA',''), "EA SPORTS FC 25", "settings"
        )
        self.backup_path = self.read_registry("backup_path") or os.path.expanduser("~\\Documents")
        self.auto_backup_interval = int(self.read_registry("auto_backup_interval") or 30)
        self.last_backup_time = self.read_registry("last_backup_time") or "Never"
        try:
            nt = self.read_registry("next_backup_time")
            self.next_backup_time = datetime.strptime(nt, "%Y-%m-%d %H:%M:%S")
        except:
            self.next_backup_time = datetime.now() + timedelta(minutes=self.auto_backup_interval)
        self.max_backups = int(self.read_registry("max_backups") or 10)

        # Window setup
        self.title(translations[self.language]['title'])
        self.geometry("450x580")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Load logo
        try:
            img = Image.open(self.resource_path("logo.png"))
            self.logo_image = CTkImage(img, size=(120,120))
        except:
            self.logo_image = None

        self.build_ui()
        self.check_fc25_status()
        self.update_countdown()

    def resource_path(self, fname):
        base = getattr(sys, '_MEIPASS', os.getcwd())
        return os.path.join(base, fname)

    def build_ui(self):
        ctk.CTkButton(self, text="⚙️", width=40, height=40, command=self.open_settings).place(x=400, y=10)
        self.last_backup_label = ctk.CTkLabel(
            self, text=f"{translations[self.language]['last_backup']}: {self.format_last_backup_time()}"
        )
        self.last_backup_label.pack(pady=(50,5))

        self.next_backup_label = ctk.CTkLabel(
            self, text=f"{translations[self.language]['next_backup']}: {self.auto_backup_interval} {translations[self.language]['minutes']}"
        )
        self.next_backup_label.pack(pady=5)

        self.manual_btn = ctk.CTkButton(
            self, text=translations[self.language]['manual_backup'], command=self.manual_backup
        )
        self.manual_btn.pack(pady=10, padx=40, fill="x")

        self.open_folder_btn = ctk.CTkButton(
            self, text=translations[self.language]['open_folder'], command=self.open_backup_folder
        )
        self.open_folder_btn.pack(pady=10, padx=40, fill="x")

        ctk.CTkLabel(self, text="─"*70, text_color="gray").pack(pady=(40,5))

        self.fc25_status_label = ctk.CTkLabel(
            self, text="Checking FC 25 status...", text_color="gray", font=("Arial",14)
        )
        self.fc25_status_label.pack(pady=(40,5))

        self.version_label = ctk.CTkLabel(
            self, text=f"{translations[self.language]['version']} {VERSION}", text_color="gray", font=("Arial",14)
        )
        self.version_label.pack(pady=(20,5))

        if self.logo_image:
            ctk.CTkLabel(self, image=self.logo_image, text="").pack(pady=(10,5))

        self.credits_label = ctk.CTkLabel(
            self, text=translations[self.language]['credits'], text_color="gold", font=("Arial",10)
        )
        self.credits_label.pack(side="bottom", pady=9)

    def manual_backup(self, event=None):
        now = datetime.now()
        iso = now.strftime("%Y-%m-%d %H:%M:%S")
        ts  = now.strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(self.backup_path, f"backup_{ts}")
        try:
            shutil.copytree(self.source_path, dest)
            self.last_backup_time = iso
            self.last_backup_label.configure(
                text=f"{translations[self.language]['last_backup']}: {self.format_last_backup_time()}"
            )
            self.next_backup_time = datetime.now() + timedelta(minutes=self.auto_backup_interval)
            self.notify("Backup Complete", f"Backup saved at {self.last_backup_time}")
            self.prune_backups()
            self.write_registry("last_backup_time", self.last_backup_time)
            self.write_registry("next_backup_time",
                                self.next_backup_time.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            self.notify("Backup Failed", str(e))

    def prune_backups(self):
        dirs = sorted(
            [d for d in os.listdir(self.backup_path) if d.startswith("backup_")],
            key=lambda d: os.path.getmtime(os.path.join(self.backup_path, d))
        )
        while len(dirs) > self.max_backups:
            oldest = dirs.pop(0)
            try:
                shutil.rmtree(os.path.join(self.backup_path, oldest))
                self.notify("Backup Pruned", f"Removed old backup: {oldest}")
            except:
                pass

    def open_backup_folder(self):
        if os.path.exists(self.backup_path):
            os.startfile(self.backup_path)

    def check_fc25_status(self):
        running = any(p.name()=="FC25.exe" for p in psutil.process_iter(['name']))
        txt = translations[self.language]['fc_running'] if running else translations[self.language]['fc_not_running']
        col = "green" if running else "red"
        self.fc25_status_label.configure(text=txt, text_color=col)
        self.after(5000, self.check_fc25_status)

    def update_countdown(self):
        diff = self.next_backup_time - datetime.now()
        mins = int(diff.total_seconds() / 60)
        if mins < 0:
            self.manual_backup()
            self.next_backup_time = datetime.now() + timedelta(minutes=self.auto_backup_interval)
            mins = self.auto_backup_interval
        self.next_backup_label.configure(
            text=f"{translations[self.language]['next_backup']}: {mins} {translations[self.language]['minutes']}"
        )
        self.after(60000, self.update_countdown)

    def open_settings(self):
        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.focus()
            return
        win = ctk.CTkToplevel(self)
        win.title(translations[self.language]['settings'])
        win.geometry("300x450")
        win.resizable(False, False)
        win.attributes("-topmost", True)

        ctk.CTkLabel(win, text=translations[self.language]['language'], font=("Arial",14))\
            .pack(pady=(20,5))
        menu = ctk.CTkOptionMenu(win, values=["🇬🇧 English","🇫🇮 Suomi"], command=self.language_selected)
        menu.pack(pady=(0,10))
        menu.set("🇬🇧 English" if self.language=="en" else "🇫🇮 Suomi")

        self.settings_folder_btn = ctk.CTkButton(
            win, text=translations[self.language]['settings_folder'], command=self.change_settings_folder
        )
        self.settings_folder_btn.pack(pady=10, padx=20, fill="x")

        self.backup_folder_btn = ctk.CTkButton(
            win, text=translations[self.language]['backup_folder'], command=self.change_backup_folder
        )
        self.backup_folder_btn.pack(pady=10, padx=20, fill="x")

        self.interval_btn = ctk.CTkButton(
            win, text=translations[self.language]['backup_interval'], command=self.change_backup_interval
        )
        self.interval_btn.pack(pady=10, padx=20, fill="x")

        self.keep_btn = ctk.CTkButton(
            win, text=f"{translations[self.language]['keep_backups']}: {self.max_backups}", command=self.change_max_backups
        )
        self.keep_btn.pack(pady=10, padx=20, fill="x")

        self.settings_window = win

    def language_selected(self, choice):
        lang = "en" if "English" in choice else "fi"
        self.write_registry("language", lang)
        self.language = lang

        self.title(translations[lang]['title'])
        self.last_backup_label.configure(
            text=f"{translations[lang]['last_backup']}: {self.format_last_backup_time()}"
        )
        self.next_backup_label.configure(
            text=f"{translations[lang]['next_backup']}: {self.auto_backup_interval} {translations[lang]['minutes']}"
        )
        self.manual_btn.configure(text=translations[lang]['manual_backup'])
        self.open_folder_btn.configure(text=translations[lang]['open_folder'])
        self.check_fc25_status()
        self.version_label.configure(text=f"{translations[lang]['version']} {VERSION}")
        self.credits_label.configure(text=translations[lang]['credits'])

        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.title(translations[lang]['settings'])
            self.settings_folder_btn.configure(text=translations[lang]['settings_folder'])
            self.backup_folder_btn.configure(text=translations[lang]['backup_folder'])
            self.interval_btn.configure(text=translations[lang]['backup_interval'])
            self.keep_btn.configure(text=f"{translations[lang]['keep_backups']}: {self.max_backups}")

    def change_settings_folder(self):
        new = filedialog.askdirectory(parent=self.settings_window, title=translations[self.language]['settings_folder'], initialdir=self.source_path)
        if new:
            self.source_path = new
            self.write_registry("source_path", new)

    def change_backup_folder(self):
        new = filedialog.askdirectory(parent=self.settings_window, title=translations[self.language]['backup_folder'], initialdir=self.backup_path)
        if new:
            self.backup_path = new
            self.write_registry("backup_path", new)

    def change_backup_interval(self):
        dlg = ctk.CTkToplevel(self.settings_window); dlg.transient(self.settings_window); dlg.grab_set()
        dlg.title(translations[self.language]['backup_interval']); dlg.geometry("300x200"); dlg.resizable(False, False)

        ctk.CTkLabel(dlg, text=translations[self.language]['backup_interval'], font=("Arial",16))\
            .pack(pady=(20,10))
        slider = ctk.CTkSlider(dlg, from_=1, to=180, number_of_steps=179)
        slider.set(self.auto_backup_interval); slider.pack(pady=10)
        lbl = ctk.CTkLabel(dlg, text=f"{self.auto_backup_interval} {translations[self.language]['minutes']}"); lbl.pack()
        slider.configure(command=lambda v: lbl.configure(text=f"{int(float(v))} {translations[self.language]['minutes']}"))
        def save_interval():
            self.auto_backup_interval = int(slider.get()); self.write_registry("auto_backup_interval", str(self.auto_backup_interval))
            self.next_backup_time = datetime.now() + timedelta(minutes=self.auto_backup_interval)
            self.next_backup_label.configure(text=f"{translations[self.language]['next_backup']}: {self.auto_backup_interval} {translations[self.language]['minutes']}")
            dlg.destroy()
        ctk.CTkButton(dlg, text=translations[self.language]['save'], command=save_interval).pack(pady=10)

    def change_max_backups(self):
        dlg = ctk.CTkToplevel(self.settings_window); dlg.transient(self.settings_window); dlg.grab_set()
        dlg.title(translations[self.language]['keep_backups']); dlg.geometry("300x200"); dlg.resizable(False, False)

        ctk.CTkLabel(dlg, text=translations[self.language]['keep_backups'], font=("Arial",16)).pack(pady=(20,10))
        slider = ctk.CTkSlider(dlg, from_=1, to=50, number_of_steps=49); slider.set(self.max_backups); slider.pack(pady=10)
        lbl = ctk.CTkLabel(dlg, text=f"{self.max_backups}"); lbl.pack()
        slider.configure(command=lambda v: lbl.configure(text=f"{int(float(v))}"))
        def save_max():
            self.max_backups = int(slider.get()); self.write_registry("max_backups", str(self.max_backups)); dlg.destroy()
        ctk.CTkButton(dlg, text=translations[self.language]['save'], command=save_max).pack(pady=10)

    def notify(self, title, msg):
        self.toaster.show_toast(title, msg, duration=5, threaded=True)

    def format_last_backup_time(self):
        if self.last_backup_time == "Never":
            return translations[self.language]['never']
        try:
            dt = datetime.strptime(self.last_backup_time, "%Y-%m-%d %H:%M:%S")
            if self.language == "fi":
                date_str = f"{dt.day}.{dt.month}.{dt.year}"
                time_str = f"{dt.hour}.{dt.minute:02d}"
                return f"{date_str} {translations['fi']['at']} {time_str}"
            else:
                locale.setlocale(locale.LC_TIME, '')
                return dt.strftime("%c")
        except:
            return self.last_backup_time

    def read_registry(self, name):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
            val, _ = winreg.QueryValueEx(key, name); winreg.CloseKey(key)
            return val
        except:
            return None

    def write_registry(self, name, val):
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH)
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, val); winreg.CloseKey(key)
        except:
            pass

    def exit_app(self, event=None):
        self.destroy()

    def center_window(self, window, w, h):
        x = (window.winfo_screenwidth() - w) // 2
        y = (window.winfo_screenheight() - h) // 2
        window.geometry(f"{w}x{h}+{x}+{y}")

if __name__ == "__main__":
    app = BackupManagerApp()
    app.mainloop()