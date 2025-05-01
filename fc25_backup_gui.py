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

# Sovelluksen versio ja GitHub-repo
VERSION = "0.3.0-alpha"
GITHUB_OWNER = "Linksutin"
GITHUB_REPO = "EA-FC25-Backup-Manager"

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
        r = requests.get(self.API_URL, timeout=10)
        r.raise_for_status()
        return r.json()

    def is_update_available(self, latest_tag):
        latest = latest_tag.lstrip('v')
        return version.parse(latest) > version.parse(self.current_version)

    def download_and_apply(self, asset_url):
        new_exe = os.path.join(os.getcwd(), "EAFC25BackupManager_new.exe")
        old_exe = os.path.realpath(sys.argv[0])

        with requests.get(asset_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(new_exe, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        bat_script = os.path.join(os.getcwd(), "update_and_restart.bat")
        with open(bat_script, "w") as f:
            f.write(f"""
@echo off
ping 127.0.0.1 -n 3 > nul
:loop
if exist "{old_exe}" (
  del /f /q "{old_exe}"
  if exist "{old_exe}" goto loop
)
rename "{new_exe}" "{os.path.basename(old_exe)}"
start "" "{os.path.basename(old_exe)}"
del "%~f0"
""")

        os.startfile(bat_script)
        sys.exit()

    def check_and_update(self):
        release = self.get_latest_release()
        tag = release.get("tag_name", "").lstrip('v')
        if self.is_update_available(tag):
            asset = next((a for a in release.get("assets", []) if a.get("name", "").endswith(".exe")), None)
            if asset:
                self.download_and_apply(asset.get("browser_download_url"))
        return False

class BackupManagerApp(ctk.CTk):
    def __init__(self):
        # Automaattinen päivitystarkistus
        try:
            GitHubUpdater(VERSION).check_and_update()
        except Exception:
            pass

        super().__init__()
        # Ikkuna-asetukset
        self.title(translations["en"]["title"])
        self.geometry("450x580")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Asetukset
        self.toaster = ToastNotifier()
        self.language = self.read_registry("language") or "en"
        self.source_path = self.read_registry("source_path") or os.path.join(os.getenv('LOCALAPPDATA'), "EA SPORTS FC 25", "settings")
        self.backup_path = self.read_registry("backup_path") or os.path.expanduser("~\\Documents")
        self.auto_backup_interval = int(self.read_registry("auto_backup_interval") or 30)
        self.last_backup_time = self.read_registry("last_backup_time") or "Never"

        next_time = self.read_registry("next_backup_time")
        if next_time:
            try:
                self.next_backup_time = datetime.strptime(next_time, "%Y-%m-%d %H:%M:%S")
            except Exception:
                self.next_backup_time = datetime.now() + timedelta(minutes=self.auto_backup_interval)
        else:
            self.next_backup_time = datetime.now() + timedelta(minutes=self.auto_backup_interval)

        # UI ja toiminnot
        self.build_ui()
        self.check_fc25_status()
        self.update_countdown()
        self.bind('<Control-q>', lambda e: self.exit_app())
        self.bind('<Control-b>', lambda e: self.manual_backup())

    def build_ui(self):
        # Asetus-painike
        ctk.CTkButton(self, text="⚙️", width=40, height=40, command=self.open_settings).place(x=400, y=10)
        # Viimeisin varmuuskopio
        self.last_backup_label = ctk.CTkLabel(self, text=f"{translations[self.language]['last_backup']}: {self.format_last_backup_time()}")
        self.last_backup_label.pack(pady=(50,5))
        # Seuraava varmuuskopio
        self.next_backup_label = ctk.CTkLabel(self, text=f"{translations[self.language]['next_backup']}: {self.auto_backup_interval} {translations[self.language]['minutes']}")
        self.next_backup_label.pack(pady=5)
        # Manuaalinen varmuuskopio & kansio
        ctk.CTkButton(self, text=translations[self.language]['manual_backup'], command=self.manual_backup).pack(pady=10, padx=40, fill="x")
        ctk.CTkButton(self, text=translations[self.language]['open_folder'], command=self.open_backup_folder).pack(pady=10, padx=40, fill="x")
        # Erotin
        ctk.CTkLabel(self, text="─"*70, text_color="gray").pack(pady=(40,5))
        # FC25 status
        self.fc25_status_label = ctk.CTkLabel(self, text="Checking FC 25 status...", text_color="gray", font=("Arial",14))
        self.fc25_status_label.pack(pady=(40,5))
        # Version
        ctk.CTkLabel(self, text=f"Version {VERSION}", text_color="gray", font=("Arial",14)).pack(pady=(20,5))
        # Credit
        ctk.CTkLabel(self, text="Code by: Linksutin | UI by: Linksu", text_color="gold", font=("Arial",18)).pack(side="bottom", pady=10)

    def open_settings(self):
        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.focus()
            return
        self.settings_window = ctk.CTkToplevel(self)
        self.settings_window.title(translations[self.language]['settings'])
        self.settings_window.geometry("300x400")
        self.settings_window.resizable(False, False)
        self.center_window(self.settings_window,300,400)
        self.settings_window.attributes("-topmost",True)
        # Asetusikkuna
        ctk.CTkLabel(self.settings_window, text=translations[self.language]['settings'], font=("Arial",20)).pack(pady=10)
        # Kielivalinta
        frame=ctk.CTkFrame(self.settings_window)
        frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(frame,text=translations[self.language]['language']).pack(side="left",padx=10)
        menu=ctk.CTkOptionMenu(frame, values=["🇬🇧 English","🇫🇮 Suomi"], command=self.language_selected)
        menu.pack(side="right")
        menu.set("🇬🇧 English" if self.language=="en" else "🇫🇮 Suomi")
        # Asetuskansio
        ctk.CTkButton(self.settings_window,text=translations[self.language]['settings_folder'],command=self.change_settings_folder).pack(pady=10,padx=20,fill="x")
        # Backup-kansio
        ctk.CTkButton(self.settings_window,text=translations[self.language]['backup_folder'],command=self.change_backup_folder).pack(pady=10,padx=20,fill="x")
        # Backup-interval
        ctk.CTkButton(self.settings_window,text=translations[self.language]['backup_interval'],command=self.change_backup_interval).pack(pady=10,padx=20,fill="x")

    def language_selected(self,choice): self.change_language("en" if "English" in choice else "fi")
    
    def change_settings_folder(self):
        new_folder=filedialog.askdirectory(title=translations[self.language]['settings_folder'],initialdir=self.source_path)
        if new_folder: self.source_path=new_folder; self.write_registry("source_path",new_folder)
    def change_backup_folder(self):
        new_folder=filedialog.askdirectory(title=translations[self.language]['backup_folder'],initialdir=self.backup_path)
        if new_folder: self.backup_path=new_folder; self.write_registry("backup_path",new_folder)
    def change_backup_interval(self):
        iw=ctk.CTkToplevel(self); iw.title(translations[self.language]['backup_interval']); iw.geometry("300x200"); iw.resizable(False,False); iw.attributes("-topmost",True)
        ctk.CTkLabel(iw,text=translations[self.language]['backup_interval'],font=("Arial",16)).pack(pady=(20,10))
        slider=ctk.CTkSlider(iw,from_=1,to=180,number_of_steps=179,command=lambda v:self._update_interval_label(v,iw));slider.pack(pady=10);slider.set(self.auto_backup_interval)
        self.interval_value=ctk.CTkLabel(iw,text=f"{self.auto_backup_interval} {translations[self.language]['minutes']}"
        );self.interval_value.pack()
        ctk.CTkButton(iw,text=translations[self.language]['save'],command=lambda:self._save_interval(iw,slider)).pack(pady=10)

    def _update_interval_label(self,v,iw): self.interval_value.configure(text=f"{int(float(v))} {translations[self.language]['minutes']}")
    def _save_interval(self,iw,slider): self.auto_backup_interval=int(slider.get()); self.write_registry("auto_backup_interval",str(self.auto_backup_interval)); self.next_backup_time=datetime.now()+timedelta(minutes=self.auto_backup_interval); self.update_countdown(); iw.destroy()

    def manual_backup(self):
        now=datetime.now(); ts=now.strftime("%Y%m%d_%H%M%S"); dest=os.path.join(self.backup_path,f"backup_{ts}")
        try:
            shutil.copytree(self.source_path,dest)
            self.last_backup_time=now.strftime("%c")
            self.last_backup_label.configure(text=f"{translations[self.language]['last_backup']}: {self.format_last_backup_time()}")
            self.next_backup_time=datetime.now()+timedelta(minutes=self.auto_backup_interval)
            self.notify("Backup Complete",f"Backup saved at {self.last_backup_time}")
        except Exception as e:
            self.notify("Backup Failed",str(e))

    def notify(self,title,msg): self.toaster.show_toast(title,msg,duration=5,threaded=True)
    def format_last_backup_time(self): return translations[self.language]['never'] if self.last_backup_time=="Never" else self.last_backup_time
    def check_fc25_status(self):
        running=any(p.name()=="FC25.exe" for p in psutil.process_iter(['name']))
        txt=translations[self.language]['fc_running'] if running else translations[self.language]['fc_not_running']
        col="green" if running else "red"
        self.fc25_status_label.configure(text=txt,text_color=col)
        self.after(5000,self.check_fc25_status)

    def update_countdown(self):
        # Päivitä countdown joka minuutti
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

    def open_backup_folder(self):
        if os.path.exists(self.backup_path): os.startfile(self.backup_path)

    def read_registry(self,name):
        try:
            key=winreg.OpenKey(winreg.HKEY_CURRENT_USER,REG_PATH,0,winreg.KEY_READ)
            val,_=winreg.QueryValueEx(key,name)
            winreg.CloseKey(key)
            return val
        except:
            return None

    def write_registry(self,name,val):
        try:
            key=winreg.CreateKey(winreg.HKEY_CURRENT_USER,REG_PATH)
            winreg.SetValueEx(key,name,0,winreg.REG_SZ,val)
            winreg.CloseKey(key)
        except:
            pass

    def exit_app(self,event=None):
        self.destroy()

    def center_window(self,window,w,h):
        x=(self.winfo_rootx()+self.winfo_width()//2)-(w//2)
        y=(self.winfo_rooty()+self.winfo_height()//2)-(h//2)
        window.geometry(f"{w}x{h}+{x}+{y}")

if __name__ == "__main__":
    app = BackupManagerApp()
    app.mainloop()