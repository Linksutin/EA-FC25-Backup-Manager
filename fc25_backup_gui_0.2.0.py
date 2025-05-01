import customtkinter as ctk
import subprocess
import sys
import os
import time
import psutil
import shutil
import ctypes
import tkinter.filedialog as filedialog
from datetime import datetime, timedelta
from win10toast import ToastNotifier
import winreg

VERSION = "0.2.0-alpha"
REG_PATH = r"Software\EAFC25BackupManager"

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

class BackupManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(translations["en"]["title"])
        self.geometry("450x580")
        self.resizable(False, False)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        try:
            if sys.platform == "win32":
                self.iconbitmap(default='new_icon.ico')
        except Exception:
            pass

        self.toaster = ToastNotifier()
        self.language = self.read_registry("language") or "en"
        self.source_path = self.read_registry("source_path") or os.path.join(os.getenv('LOCALAPPDATA'), "EA SPORTS FC 25", "settings")
        self.backup_path = self.read_registry("backup_path") or os.path.expanduser("~\\Documents")
        self.auto_backup_interval = int(self.read_registry("auto_backup_interval") or 30)

        self.last_backup_time = self.read_registry("last_backup_time") or "Never"

        next_backup_from_reg = self.read_registry("next_backup_time")
        if next_backup_from_reg:
            try:
                self.next_backup_time = datetime.strptime(next_backup_from_reg, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                self.next_backup_time = datetime.now() + timedelta(minutes=self.auto_backup_interval)
        else:
            self.next_backup_time = datetime.now() + timedelta(minutes=self.auto_backup_interval)

        self.build_ui()
        self.check_fc25_status()
        self.update_countdown()

        self.bind('<Control-q>', lambda event: self.exit_app())
        self.bind('<Control-b>', lambda event: self.manual_backup())

    def manual_backup(self, event=None):
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        dest_folder = os.path.join(self.backup_path, f"backup_{timestamp}")

        try:
            shutil.copytree(self.source_path, dest_folder)

            self.last_backup_time = now.strftime("%c")  # käyttäjän Windows-asetuksella
            self.last_backup_label.configure(text=f"{translations[self.language]['last_backup']}: {self.format_last_backup_time()}")

            self.next_backup_time = datetime.now() + timedelta(minutes=self.auto_backup_interval)

            self.notify("Backup Complete", f"Backup saved at {self.last_backup_time}")

            # Tallennetaan myös rekisteriin
            self.write_registry("last_backup_time", self.last_backup_time)
            self.write_registry("next_backup_time", self.next_backup_time.strftime("%Y-%m-%d %H:%M:%S"))

        except Exception as e:
            self.notify("Backup Failed", str(e))

    def auto_backup(self):
        self.manual_backup()

    def build_ui(self):
        self.settings_button = ctk.CTkButton(self, text="⚙️", width=40, height=40, command=self.open_settings)
        self.settings_button.place(x=400, y=10)

        self.last_backup_label = ctk.CTkLabel(self, text=f"{translations[self.language]['last_backup']}: {self.format_last_backup_time()}")
        self.last_backup_label.pack(pady=(50,5))

        self.next_backup_label = ctk.CTkLabel(self, text=f"{translations[self.language]['next_backup']}: {self.auto_backup_interval} {translations[self.language]['minutes']}")
        self.next_backup_label.pack(pady=5)

        self.manual_backup_button = self.create_button(translations[self.language]['manual_backup'], self.manual_backup)
        self.manual_backup_button.pack(pady=10, padx=40, fill="x")

        self.open_folder_button = self.create_button(translations[self.language]['open_folder'], self.open_backup_folder)
        self.open_folder_button.pack(pady=10, padx=40, fill="x")

        self.divider = ctk.CTkLabel(self, text="─" * 70, text_color="gray")
        self.divider.pack(pady=(40,5))

        self.fc25_status_label = ctk.CTkLabel(self, text="Checking FC 25 status...", text_color="gray", font=("Arial", 14))
        self.fc25_status_label.pack(pady=(40,5))

        self.version_label = ctk.CTkLabel(self, text=f"Version {VERSION}", text_color="gray", font=("Arial", 14))
        self.version_label.pack(pady=(20,5))

        self.credits_label = ctk.CTkLabel(self, text="Code by: mryoshl | UI by: Linksu", text_color="gold", font=("Arial", 18))
        self.credits_label.pack(side="bottom", pady=10)

    def create_button(self, text, command, master=None):
        return ctk.CTkButton(master if master else self, text=text, command=command, fg_color="#1f6aa5", hover_color="#144272")

    def notify(self, title, message):
        self.toaster.show_toast(title, message, duration=5, threaded=True)

    def update_countdown(self):
        diff = self.next_backup_time - datetime.now()
        minutes_left = int(diff.total_seconds() / 60)
        if minutes_left < 0:
            self.auto_backup()
            self.next_backup_time = datetime.now() + timedelta(minutes=self.auto_backup_interval)
            minutes_left = self.auto_backup_interval
        self.next_backup_label.configure(text=f"{translations[self.language]['next_backup']}: {minutes_left} {translations[self.language]['minutes']}")
        self.after(60000, self.update_countdown)

    def check_fc25_status(self):
        running = any(proc.name() == "FC25.exe" for proc in psutil.process_iter(['name']))
        if running:
            self.fc25_status_label.configure(text=translations[self.language]['fc_running'], text_color="green")
        else:
            self.fc25_status_label.configure(text=translations[self.language]['fc_not_running'], text_color="red")
        self.after(5000, self.check_fc25_status)

    def open_backup_folder(self):
        if os.path.exists(self.backup_path):
            os.startfile(self.backup_path)

    def open_settings(self):
        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.focus()
            return

        self.settings_window = ctk.CTkToplevel(self)
        self.settings_window.title(translations[self.language]['settings'])
        self.settings_window.geometry("300x400")
        self.settings_window.resizable(False, False)
        self.center_window(self.settings_window, 300, 400)
        self.settings_window.attributes("-topmost", True)

        self.build_settings_ui()

    def build_settings_ui(self):
        for widget in self.settings_window.winfo_children():
            widget.destroy()

        ctk.CTkLabel(self.settings_window, text=translations[self.language]['settings'], font=("Arial", 20)).pack(pady=(10,10))

        self.language_frame = ctk.CTkFrame(self.settings_window)
        self.language_frame.pack(pady=10, padx=20, fill="x")

        self.language_label = ctk.CTkLabel(self.language_frame, text=translations[self.language]['language'])
        self.language_label.pack(side="left", padx=10)

        self.language_menu = ctk.CTkOptionMenu(
            self.language_frame,
            values=["🇬🇧 English", "🇫🇮 Suomi"],
            command=self.language_selected
        )
        self.language_menu.pack(side="right")
        self.language_menu.set("🇬🇧 English" if self.language == "en" else "🇫🇮 Suomi")

        self.settings_folder_button = self.create_button(translations[self.language]['settings_folder'], self.change_settings_folder, master=self.settings_window)
        self.settings_folder_button.pack(pady=10, padx=20, fill="x")

        self.backup_folder_button = self.create_button(translations[self.language]['backup_folder'], self.change_backup_folder, master=self.settings_window)
        self.backup_folder_button.pack(pady=10, padx=20, fill="x")

        self.backup_interval_button = self.create_button(translations[self.language]['backup_interval'], self.change_backup_interval, master=self.settings_window)
        self.backup_interval_button.pack(pady=10, padx=20, fill="x")

    def change_settings_folder(self):
        default_path = os.path.join(os.getenv('LOCALAPPDATA'), "EA SPORTS FC 25", "settings")
        new_folder = filedialog.askdirectory(title=translations[self.language]['settings_folder'], initialdir=default_path, parent=self.settings_window)
        if new_folder:
            self.source_path = new_folder
            self.write_registry("source_path", new_folder)

    def change_backup_folder(self):
        new_folder = filedialog.askdirectory(title=translations[self.language]['backup_folder'], initialdir=self.backup_path, parent=self.settings_window)
        if new_folder:
            self.backup_path = new_folder
            self.write_registry("backup_path", new_folder)

    def change_backup_interval(self):
        if hasattr(self, 'interval_window') and self.interval_window.winfo_exists():
            self.interval_window.focus()
            return

        self.settings_window.attributes("-topmost", False)

        self.interval_window = ctk.CTkToplevel(self.settings_window)
        self.interval_window.title(translations[self.language]['backup_interval'])
        self.interval_window.geometry("300x250")
        self.interval_window.resizable(False, False)
        self.center_window(self.interval_window, 300, 250)
        self.interval_window.lift()
        self.interval_window.focus_force()
        self.interval_window.attributes("-topmost", True)

        label = ctk.CTkLabel(self.interval_window, text=translations[self.language]['backup_interval'], font=("Arial", 16))
        label.pack(pady=(20, 10))

        self.interval_entry = ctk.CTkSlider(self.interval_window, from_=1, to=180, number_of_steps=179, command=self.update_interval_label)
        self.interval_entry.pack(pady=10)
        self.interval_entry.set(self.auto_backup_interval)

        self.interval_value_label = ctk.CTkLabel(self.interval_window, text=f"{self.auto_backup_interval} {translations[self.language]['minutes']}")
        self.interval_value_label.pack(pady=10)

        save_button = ctk.CTkButton(self.interval_window, text=translations[self.language]['save'], command=self.save_new_interval)
        save_button.pack(pady=(20, 10))

        self.interval_window.protocol("WM_DELETE_WINDOW", self.restore_settings_window)

    def restore_settings_window(self):
        self.settings_window.lift()
        self.settings_window.attributes("-topmost", True)
        self.interval_window.destroy()

    def update_interval_label(self, value):
        self.interval_value_label.configure(text=f"{int(value)} {translations[self.language]['minutes']}")

    def save_new_interval(self):
        new_interval = int(self.interval_entry.get())
        self.auto_backup_interval = new_interval
        self.write_registry("auto_backup_interval", str(new_interval))
        self.next_backup_time = datetime.now() + timedelta(minutes=new_interval)
        self.update_countdown()
        self.restore_settings_window()

    def language_selected(self, choice):
        if "English" in choice:
            self.change_language("en")
        elif "Suomi" in choice:
            self.change_language("fi")

    def change_language(self, lang):
        self.language = lang
        self.write_registry("language", lang)
        self.rebuild_ui()

        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.destroy()
            self.open_settings()

    def rebuild_ui(self):
        self.last_backup_label.configure(text=f"{translations[self.language]['last_backup']}: {self.format_last_backup_time()}")
        self.next_backup_label.configure(text=f"{translations[self.language]['next_backup']}: {self.auto_backup_interval} {translations[self.language]['minutes']}")
        self.manual_backup_button.configure(text=translations[self.language]['manual_backup'])
        self.open_folder_button.configure(text=translations[self.language]['open_folder'])
        self.title(translations[self.language]['title'])
        self.update_fc25_status_text()

    def format_last_backup_time(self):
        if self.last_backup_time == "Never":
            return translations[self.language]['never']
        return self.last_backup_time

    def update_fc25_status_text(self):
        running = any(proc.name() == "FC25.exe" for proc in psutil.process_iter(['name']))
        if running:
            self.fc25_status_label.configure(text=translations[self.language]['fc_running'], text_color="green")
        else:
            self.fc25_status_label.configure(text=translations[self.language]['fc_not_running'], text_color="red")

    def center_window(self, window, width, height):
        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()
        parent_width = self.winfo_width()
        parent_height = self.winfo_height()
        x = parent_x + (parent_width // 2) - (width // 2)
        y = parent_y + (parent_height // 2) - (height // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")

    def read_registry(self, name):
        try:
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
            value, regtype = winreg.QueryValueEx(registry_key, name)
            winreg.CloseKey(registry_key)
            return value
        except WindowsError:
            return None

    def write_registry(self, name, value):
        try:
            registry_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH)
            winreg.SetValueEx(registry_key, name, 0, winreg.REG_SZ, value)
            winreg.CloseKey(registry_key)
        except WindowsError as e:
            print(e)

    def exit_app(self, event=None):
        self.destroy()

if __name__ == "__main__":
    app = BackupManagerApp()
    app.mainloop()