import os
import shutil
import time
import psutil
import logging
import keyboard
import threading
import configparser
from win10toast import ToastNotifier
import subprocess

# ==== ILMOITUKSET ====
toaster = ToastNotifier()

# ==== CONFIG-ININ LUONTI JOS PUUTTUU ====
CONFIG_FILE = 'config.ini'

def create_default_config():
    config = configparser.ConfigParser()
    config['PATHS'] = {
        'source': r'C:\Users\Linksutin\AppData\Local\EA SPORTS FC 25\settings',
        'backup': r'E:\HAULA'
    }
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    toaster.show_toast("EA FC 25 Backup", "Default config.ini created. Please edit paths!", duration=5)
    print("Default config.ini created. Please edit the file and restart the program.")
    try:
        subprocess.Popen(['notepad.exe', CONFIG_FILE])
    except Exception as e:
        print(f"Could not open Notepad automatically: {e}")
    exit()  # Lopeta ohjelma että käyttäjä muokkaa polut ennen jatkamista

if not os.path.exists(CONFIG_FILE):
    create_default_config()

# ==== CONFIGIN LUKEMINEN ====
config = configparser.ConfigParser()
config.read(CONFIG_FILE)

if 'PATHS' not in config:
    raise Exception("Error: 'PATHS' section not found in config.ini!")

SOURCE_FOLDER = config['PATHS']['source']
BACKUP_FOLDER = config['PATHS']['backup']
BACKUPS_DIR = os.path.join(BACKUP_FOLDER, "backups")
os.makedirs(BACKUPS_DIR, exist_ok=True)

# ==== LOKITIEDOSTO JA RAJAUS ====
LOG_FILE = os.path.join(BACKUP_FOLDER, 'fc25_backup_log.txt')
logging.basicConfig(filename=LOG_FILE, 
                    level=logging.INFO, format='%(asctime)s - %(message)s')

def clean_log(max_size=5*1024*1024):  # 5 MB
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > max_size:
        open(LOG_FILE, 'w').close()
        logging.info("Log file cleared due to size limit.")

def is_fc25_running():
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == 'FC25.exe':
            return True
    return False

def clean_old_backups(days=30):
    now = time.time()
    for folder in os.listdir(BACKUPS_DIR):
        folder_path = os.path.join(BACKUPS_DIR, folder)
        if os.path.isdir(folder_path):
            if os.path.getmtime(folder_path) < now - (days * 86400):
                shutil.rmtree(folder_path)
                logging.info(f"Old backup deleted: {folder}")

def backup_settings():
    clean_log()  # Puhdista loki tarvittaessa

    if os.path.exists(SOURCE_FOLDER):
        try:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            backup_path = os.path.join(BACKUPS_DIR, f"settingsbackup_{timestamp}")
            shutil.copytree(SOURCE_FOLDER, backup_path, dirs_exist_ok=True)
            logging.info(f"Backup completed successfully at {timestamp}.")
            toaster.show_toast("EA FC 25 Backup", f"Backup completed at {timestamp}", duration=5)
        except shutil.Error as e:
            logging.error(f"Backup shutil error: {e}")
            toaster.show_toast("EA FC 25 Backup", "Backup error!", duration=5)
        except Exception as e:
            logging.error(f"Backup general error: {e}")
            toaster.show_toast("EA FC 25 Backup", "Backup error!", duration=5)
    else:
        logging.warning(f"Source folder {SOURCE_FOLDER} not found.")
        toaster.show_toast("EA FC 25 Backup", "Source folder not found!", duration=5)

    clean_old_backups()

def listen_for_hotkeys():
    while True:
        if keyboard.is_pressed('ctrl+b'):
            logging.info("Ctrl+B pressed. Manual backup started.")
            backup_settings()
            time.sleep(1)
        elif keyboard.is_pressed('ctrl+q'):
            logging.info("Ctrl+Q pressed. Exiting script.")
            toaster.show_toast("EA FC 25 Backup", "Backup script closed.", duration=3)
            os._exit(0)
        time.sleep(0.1)

def main():
    threading.Thread(target=listen_for_hotkeys, daemon=True).start()

    while True:
        if is_fc25_running():
            logging.info("FC25.exe is running. Monitoring game...")
            last_backup = 0

            while is_fc25_running():
                current_time = time.time()
                if current_time - last_backup >= 1800:  # 30 minuuttia
                    backup_settings()
                    last_backup = current_time
                time.sleep(10)

            logging.info("FC25.exe closed. Final backup...")
            backup_settings()

        else:
            time.sleep(30)

if __name__ == "__main__":
    main()