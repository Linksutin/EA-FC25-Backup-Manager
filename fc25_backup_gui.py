import os
import shutil
import configparser
import subprocess
from datetime import datetime, timedelta
import customtkinter as ctk
from win10toast import ToastNotifier
import tkinter.filedialog as filedialog
import sys

# Versio
VERSION = "1.0.0"

class BackupManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Ikkunan asetukset
        self.title(f"EA FC 25 Backup Manager v{VERSION}")
        self.geometry("400x420")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Ladataan asetukset (tai kysytään käyttäjältä)
        self.config_file = "config.ini"
        self.config = configparser.ConfigParser()
        self.load_or_create_config()

        # Käyttöliittymä
        last_backup_text = self.config['Settings'].get('last_backup', 'Never')
        self.last_backup_label = ctk.CTkLabel(self, text=f"Last backup: {last_backup_text}")
        self.last_backup_label.pack(pady=(20,5))

        self.next_backup_label = ctk.CTkLabel(self, text="Next backup in: 30 minutes")
        self.next_backup_label.pack(pady=(0,15))

        backup_button = ctk.CTkButton(self, text="Start Manual Backup", command=self.manual_backup)
        backup_button.pack(pady=5, padx=20, fill="x")

        open_folder_button = ctk.CTkButton(self, text="Open Backup Folder", command=self.open_backup_folder)
        open_folder_button.pack(pady=5, padx=20, fill="x")

        edit_config_button = ctk.CTkButton(self, text="Edit Config File", command=self.edit_config)
        edit_config_button.pack(pady=5, padx=20, fill="x")

        exit_button = ctk.CTkButton(self, text="Exit", command=self.exit_app)
        exit_button.pack(pady=5, padx=20, fill="x")

        credit_label = ctk.CTkLabel(self, text="Code by: mryoshl | UI by: Linksu", text_color="gold")
        credit_label.pack(pady=(10, 0))

        version_label = ctk.CTkLabel(self, text=f"Version {VERSION}", text_color="gray")
        version_label.pack(pady=(0, 5))

        # Ilmoitusobjekti
        self.notifier = ToastNotifier()

        # Ajastimet
        self.next_backup_time = datetime.now() + timedelta(minutes=30)
        self.auto_event = self.after(30 * 60 * 1000, self.auto_backup)
        self.after(1000, self.update_countdown)

    def load_or_create_config(self):
        if not os.path.exists(self.config_file):
            self.ask_for_folders()
        else:
            self.config.read(self.config_file)
            if 'Paths' not in self.config or 'source_path' not in self.config['Paths'] or 'backup_path' not in self.config['Paths']:
                self.ask_for_folders()

        self.source_path = self.config['Paths']['source_path']
        self.backup_path = self.config['Paths']['backup_path']
        os.makedirs(self.backup_path, exist_ok=True)

    def ask_for_folders(self):
        local_appdata = os.getenv('LOCALAPPDATA')
        default_fc25_settings = os.path.join(local_appdata, "EA SPORTS FC 25", "Settings")

        if os.path.exists(default_fc25_settings):
            initial_dir = default_fc25_settings
        else:
            initial_dir = local_appdata

        source = filedialog.askdirectory(
            title="Select your EA FC 25 Settings folder",
            initialdir=initial_dir
        )
        backup = filedialog.askdirectory(
            title="Select where to save backups",
            initialdir=os.path.expanduser("~\\Documents")
        )

        if not source or not backup:
            self.destroy()
            sys.exit("Folders not selected. Exiting.")

        self.config['Paths'] = {
            'source_path': source,
            'backup_path': backup
        }
        self.config['Settings'] = {'last_backup': 'Never'}

        with open(self.config_file, 'w') as f:
            self.config.write(f)

    def manual_backup(self):
        if hasattr(self, 'auto_event') and self.auto_event is not None:
            try:
                self.after_cancel(self.auto_event)
            except Exception:
                pass
            self.auto_event = None

        self.perform_backup(manual=True)
        self.next_backup_time = datetime.now() + timedelta(minutes=30)
        self.auto_event = self.after(30 * 60 * 1000, self.auto_backup)

    def auto_backup(self):
        self.perform_backup(manual=False)
        self.next_backup_time = datetime.now() + timedelta(minutes=30)
        self.auto_event = self.after(30 * 60 * 1000, self.auto_backup)

    def perform_backup(self, manual=False):
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        dest_folder = os.path.join(self.backup_path, f"backup_{timestamp}")

        try:
            if not os.path.exists(self.source_path):
                raise FileNotFoundError(f"Source path not found: {self.source_path}")
            shutil.copytree(self.source_path, dest_folder)
        except Exception as e:
            if os.path.exists(dest_folder):
                try:
                    shutil.rmtree(dest_folder)
                except Exception:
                    pass
            self.notifier.show_toast("EA FC 25 Backup Manager",
                                     f"Backup failed: {e}",
                                     duration=5, threaded=True)
            return

        time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        self.last_backup_label.configure(text=f"Last backup: {time_str}")
        self.config['Settings']['last_backup'] = time_str
        with open(self.config_file, 'w') as f:
            self.config.write(f)

        title = "EA FC 25 Backup Manager"
        message = f"{'Manual' if manual else 'Automatic'} backup completed at {time_str}"
        self.notifier.show_toast(title, message, duration=5, threaded=True)

    def update_countdown(self):
        if hasattr(self, 'next_backup_time'):
            diff = self.next_backup_time - datetime.now()
            minutes_left = int(diff.total_seconds() // 60)
            if minutes_left < 0:
                minutes_left = 0
            self.next_backup_label.configure(text=f"Next backup in: {minutes_left} minutes")
        self.after(1000, self.update_countdown)

    def open_backup_folder(self):
        try:
            os.startfile(self.backup_path)
        except Exception:
            subprocess.Popen(["explorer", self.backup_path])

    def edit_config(self):
        config_path = os.path.abspath(self.config_file)
        try:
            os.startfile(config_path)
        except Exception:
            subprocess.Popen(["notepad", config_path])
        self.notifier.show_toast("EA FC 25 Backup Manager",
                                 "Config file opened. Please restart the app after saving changes.",
                                 duration=5, threaded=True)

    def exit_app(self):
        self.destroy()

# Käynnistetään sovellus
if __name__ == "__main__":
    app = BackupManagerApp()

    # Asetetaan ikoni käyttöön .exe-paketeille
    if getattr(sys, 'frozen', False):
        app.iconbitmap(os.path.join(sys._MEIPASS, "new_icon.ico"))

    app.mainloop()
