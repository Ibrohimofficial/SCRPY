#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scrcpy/AirPlay GUI - Android va iPhone/iPad ekranini ko'rish uchun oson ilova.

- Android tab: scrcpy orqali USB yoki Wi-Fi bilan ulanadi.
- iPhone/iPad tab: AirPlay receiver (uxplay-windows) orqali ulanadi.

Kod yozish, terminal ochish kerak emas - hammasi tugmalar orqali.
"""

import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont
import subprocess
import threading
import os
import sys
import re
import json
import zipfile
import urllib.request
import webbrowser

# ====== UMUMIY SOZLAMALAR ======
def get_app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

APP_DIR = get_app_dir()

# ---- Android / scrcpy sozlamalari ----
SCRCPY_DIR = os.path.join(APP_DIR, "scrcpy-bin")
SCRCPY_EXE = os.path.join(SCRCPY_DIR, "scrcpy.exe")
ADB_EXE = os.path.join(SCRCPY_DIR, "adb.exe")
SCRCPY_DOWNLOAD_URL = "https://github.com/Genymobile/scrcpy/releases/download/v3.1/scrcpy-win64-v3.1.zip"

# ---- iOS / AirPlay (uxplay-windows) sozlamalari ----
AIRPLAY_DIR = os.path.join(APP_DIR, "airplay-bin")
AIRPLAY_EXE = os.path.join(AIRPLAY_DIR, "uxplay-windows.exe")
AIRPLAY_GITHUB_API = "https://api.github.com/repos/leapbtw/uxplay-windows/releases/latest"
AIRPLAY_INSTALLER_NAME_HINT = "installer"  # asset nomida shu so'z bo'lsa, o'shani yuklaymiz

# ---- Rang va shrift sxemasi ----
BG_COLOR = "#1e1f29"
CARD_COLOR = "#282a3a"
ACCENT = "#6c63ff"
ACCENT_HOVER = "#8077ff"
ACCENT_IOS = "#3a9bfc"
TEXT_COLOR = "#f1f1f6"
SUBTEXT_COLOR = "#9a9ab0"
SUCCESS_COLOR = "#4caf82"
ERROR_COLOR = "#e15c5c"
LINK_COLOR = "#7c9cff"
FONT_NAME = "Segoe UI"

# ---- Ishlab chiquvchi ma'lumotlari ----
STUDIO_NAME = "Ajib Studio"
STUDIO_URL = "https://ajibstudio.uz/"


# =========================================================
# Yordamchi funksiyalar
# =========================================================
def run_hidden(cmd_list, timeout=15):
    """Buyruqni Windows konsol oynasini ko'rsatmasdan ishga tushiradi."""
    creationflags = 0
    startupinfo = None
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    try:
        result = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags,
            startupinfo=startupinfo,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Vaqt tugadi (timeout)"
    except FileNotFoundError:
        return -2, "", "Fayl topilmadi"
    except Exception as e:
        return -3, "", str(e)


def launch_detached(cmd_list, cwd=None):
    """Dasturni asosiy ilovadan mustaqil (ajratilgan) holda ishga tushiradi."""
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.DETACHED_PROCESS
    subprocess.Popen(
        cmd_list,
        cwd=cwd,
        creationflags=creationflags if os.name == "nt" else 0,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def is_process_running(exe_name):
    """Windows tasklist orqali jarayon ishlab turganini tekshiradi."""
    if os.name != "nt":
        return False
    code, out, _ = run_hidden(["tasklist", "/FI", f"IMAGENAME eq {exe_name}"], timeout=8)
    return code == 0 and exe_name.lower() in out.lower()


def kill_process(exe_name):
    """Windows taskkill orqali jarayonni to'xtatadi."""
    if os.name != "nt":
        return
    run_hidden(["taskkill", "/F", "/IM", exe_name], timeout=8)


def is_valid_ip_port(text):
    """IP:PORT formatini tekshiradi. Port ko'rsatilmasa, default 5555 qo'shiladi."""
    text = text.strip()
    if not text:
        return None
    if ":" not in text:
        text = text + ":5555"
    ip_part, port_part = text.rsplit(":", 1)
    ip_pattern = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
    m = re.match(ip_pattern, ip_part)
    if not m:
        return None
    for g in m.groups():
        if int(g) > 255:
            return None
    if not port_part.isdigit():
        return None
    return f"{ip_part}:{port_part}"


def get_pc_hostname():
    try:
        import socket
        return socket.gethostname()
    except Exception:
        return "kompyuter"


# =========================================================
# Asosiy ilova
# =========================================================
class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ajib Ekran Ulagich - Android va iPhone/iPad")
        self.geometry("600x760")
        self.minsize(600, 760)
        self.configure(bg=BG_COLOR)
        self.resizable(False, False)

        self._set_app_icon()
        self._build_tabs()

    def _set_app_icon(self):
        """Ilova ikonini o'rnatadi. PyInstaller bilan yig'ilganda fayl
        vaqtinchalik papkaga (_MEIPASS) chiqariladi, oddiy holatda skript yonida bo'ladi."""
        try:
            # Mumkin bo'lgan joylarni tekshiramiz
            candidates = []
            if hasattr(sys, "_MEIPASS"):
                candidates.append(os.path.join(sys._MEIPASS, "app_icon.ico"))
            candidates.append(os.path.join(APP_DIR, "app_icon.ico"))

            for icon_path in candidates:
                if os.path.isfile(icon_path):
                    self.iconbitmap(icon_path)
                    return
        except Exception:
            pass  # ikon topilmasa, standart ikon ishlatiladi

    def _build_tabs(self):
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure(
            "Custom.TNotebook", background=BG_COLOR, borderwidth=0
        )
        style.configure(
            "Custom.TNotebook.Tab",
            background=CARD_COLOR, foreground=TEXT_COLOR,
            padding=[20, 12], font=(FONT_NAME, 12, "bold")
        )
        style.map(
            "Custom.TNotebook.Tab",
            background=[("selected", ACCENT)],
            foreground=[("selected", "white")],
        )

        # ---- Pastki footer: ishlab chiquvchi yozuvi (ikkala tabda ham ko'rinadi) ----
        footer = tk.Frame(self, bg=BG_COLOR)
        footer.pack(side="bottom", fill="x", pady=(4, 8))

        credit_frame = tk.Frame(footer, bg=BG_COLOR)
        credit_frame.pack()

        tk.Label(
            credit_frame, text="Ushbu dastur ", bg=BG_COLOR, fg=SUBTEXT_COLOR,
            font=(FONT_NAME, 9)
        ).pack(side="left")

        link_font = tkfont.Font(family=FONT_NAME, size=9, underline=True)
        self.studio_link = tk.Label(
            credit_frame, text=STUDIO_NAME, bg=BG_COLOR, fg=LINK_COLOR,
            font=link_font, cursor="hand2"
        )
        self.studio_link.pack(side="left")
        self.studio_link.bind("<Button-1>", lambda e: self._open_studio_link())
        # Sichqoncha ustiga kelganda rangini o'zgartirish (hover effekti)
        self.studio_link.bind("<Enter>", lambda e: self.studio_link.configure(fg="#a9c0ff"))
        self.studio_link.bind("<Leave>", lambda e: self.studio_link.configure(fg=LINK_COLOR))

        tk.Label(
            credit_frame, text=" jamoasi tomonidan ishlab chiqildi",
            bg=BG_COLOR, fg=SUBTEXT_COLOR, font=(FONT_NAME, 9)
        ).pack(side="left")

        # ---- Notebook (tablar) - qolgan joyni egallaydi ----
        notebook = ttk.Notebook(self, style="Custom.TNotebook")
        notebook.pack(fill="both", expand=True)

        android_frame = tk.Frame(notebook, bg=BG_COLOR)
        ios_frame = tk.Frame(notebook, bg=BG_COLOR)

        notebook.add(android_frame, text="🤖  Android")
        notebook.add(ios_frame, text="🍎  iPhone / iPad")

        self.android_tab = AndroidTab(android_frame, self)
        self.ios_tab = IOSTab(ios_frame, self)

    def _open_studio_link(self):
        try:
            webbrowser.open(STUDIO_URL)
        except Exception:
            pass


# =========================================================
# ANDROID TAB (scrcpy)
# =========================================================
class AndroidTab:
    def __init__(self, parent, root):
        self.parent = parent
        self.root = root

        self.connection_mode = tk.StringVar(value="usb")
        self.ip_value = tk.StringVar()
        self.status_text = tk.StringVar(value="Tayyor. Ulanish usulini tanlang.")
        self.extra_flags = {
            "stay_awake": tk.BooleanVar(value=True),
            "fullscreen": tk.BooleanVar(value=False),
            "always_top": tk.BooleanVar(value=False),
            "show_touches": tk.BooleanVar(value=False),
        }

        self._needs_download = False
        self._check_scrcpy_exists()
        self._build_ui()

        if self._needs_download:
            threading.Thread(target=self._download_scrcpy, daemon=True).start()

    # ---------- Tekshiruvlar ----------
    def _check_scrcpy_exists(self):
        if os.path.isfile(SCRCPY_EXE) and os.path.isfile(ADB_EXE):
            return
        self._needs_download = True

    def _download_scrcpy(self):
        zip_path = os.path.join(APP_DIR, "_scrcpy_temp.zip")
        try:
            self.root.after(0, lambda: self.set_status(
                "Birinchi marta ishga tushirilmoqda: scrcpy yuklab olinmoqda (~25 MB)...",
                SUBTEXT_COLOR))
            self.root.after(0, lambda: self.connect_btn.configure(state="disabled"))

            os.makedirs(SCRCPY_DIR, exist_ok=True)

            def reporthook(block_num, block_size, total_size):
                if total_size > 0:
                    percent = min(100, int(block_num * block_size * 100 / total_size))
                    self.root.after(0, lambda p=percent: self.set_status(
                        f"Yuklab olinmoqda... {p}%", SUBTEXT_COLOR))

            urllib.request.urlretrieve(SCRCPY_DOWNLOAD_URL, zip_path, reporthook)

            self.root.after(0, lambda: self.set_status("Ochib joylashtirilmoqda...", SUBTEXT_COLOR))
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                top_level_dirs = set(n.split("/")[0] for n in names if "/" in n)
                zf.extractall(APP_DIR if not top_level_dirs else SCRCPY_DIR)
                if top_level_dirs:
                    extracted_root = os.path.join(SCRCPY_DIR, list(top_level_dirs)[0])
                    if os.path.isdir(extracted_root):
                        for fname in os.listdir(extracted_root):
                            src = os.path.join(extracted_root, fname)
                            dst = os.path.join(SCRCPY_DIR, fname)
                            if not os.path.exists(dst):
                                os.replace(src, dst)

            os.remove(zip_path)

            if os.path.isfile(SCRCPY_EXE):
                self.root.after(0, lambda: self.set_status(
                    "Tayyor! Endi ulanish usulini tanlab, ULASH tugmasini bosing.",
                    SUCCESS_COLOR))
            else:
                self.root.after(0, lambda: self.set_status(
                    "Yuklab olindi, lekin scrcpy.exe topilmadi. Internetni tekshirib qaytadan urinib ko'ring.",
                    ERROR_COLOR))
        except Exception as e:
            self.root.after(0, lambda: self.set_status(
                f"Yuklab olishda xato: {e}\nInternetni tekshirib, ilovani qayta ishga tushiring.",
                ERROR_COLOR))
        finally:
            self.root.after(0, lambda: self.connect_btn.configure(state="normal"))

    # ---------- UI qurish ----------
    def _build_ui(self):
        p = self.parent
        header = tk.Frame(p, bg=BG_COLOR)
        header.pack(fill="x", padx=28, pady=(20, 10))

        tk.Label(
            header, text="📱 Scrcpy Ulagich", bg=BG_COLOR, fg=TEXT_COLOR,
            font=(FONT_NAME, 20, "bold")
        ).pack(anchor="w")
        tk.Label(
            header, text="Android telefon/planshet ekranini kompyuterda ko'rish",
            bg=BG_COLOR, fg=SUBTEXT_COLOR, font=(FONT_NAME, 10)
        ).pack(anchor="w", pady=(2, 0))

        self.connection_cards_frame, card1 = self._make_card(p, "1-qadam: Ulanish usulini tanlang")
        row = tk.Frame(card1, bg=CARD_COLOR)
        row.pack(fill="x", pady=(8, 0))

        self.usb_btn = self._radio_card(
            row, "🔌  USB orqali", "Kabel bilan ulang va tugmani bosing",
            "usb", side="left"
        )
        self.wifi_btn = self._radio_card(
            row, "📶  Wi-Fi orqali", "Telefon IP manzilini kiriting",
            "wifi", side="right"
        )

        self.ip_card_outer, self.ip_card_inner = self._make_card(p, "2-qadam: Telefon IP manzili")

        tk.Label(
            self.ip_card_inner,
            text="Sozlamalar → Wi-Fi → ulangan tarmoq → IP manzil (masalan: 192.168.1.25)",
            bg=CARD_COLOR, fg=SUBTEXT_COLOR, font=(FONT_NAME, 9)
        ).pack(anchor="w")

        ip_row = tk.Frame(self.ip_card_inner, bg=CARD_COLOR)
        ip_row.pack(fill="x", pady=(8, 0))
        self.ip_entry = tk.Entry(
            ip_row, textvariable=self.ip_value, font=(FONT_NAME, 13),
            bg="#33354a", fg=TEXT_COLOR, insertbackground=TEXT_COLOR,
            relief="flat", width=28
        )
        self.ip_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))

        self.ip_card_outer.pack_forget()

        _, card3 = self._make_card(p, "Qo'shimcha sozlamalar (ixtiyoriy)")
        opts = tk.Frame(card3, bg=CARD_COLOR)
        opts.pack(fill="x", pady=(4, 0))

        self._checkbox(opts, "Ekran o'chmasin (uyg'oq turish)", self.extra_flags["stay_awake"])
        self._checkbox(opts, "To'liq ekran rejimida ochish", self.extra_flags["fullscreen"])
        self._checkbox(opts, "Doim ustda turish", self.extra_flags["always_top"])
        self._checkbox(opts, "Ekranda tegishlarni ko'rsatish", self.extra_flags["show_touches"])

        self.connect_btn = tk.Button(
            p, text="🚀  ULASH",
            command=self.on_connect_clicked,
            bg=ACCENT, fg="white", activebackground=ACCENT_HOVER,
            font=(FONT_NAME, 14, "bold"), relief="flat", cursor="hand2",
            padx=20, pady=12
        )
        self.connect_btn.pack(fill="x", padx=28, pady=(14, 6))

        self.status_label = tk.Label(
            p, textvariable=self.status_text, bg=BG_COLOR, fg=SUBTEXT_COLOR,
            font=(FONT_NAME, 10), wraplength=540, justify="left"
        )
        self.status_label.pack(fill="x", padx=28, pady=(0, 14))

        self._select_mode("usb")

    def _make_card(self, parent, title):
        card = tk.Frame(parent, bg=CARD_COLOR)
        card.pack(fill="x", padx=28, pady=7)
        inner_pad = tk.Frame(card, bg=CARD_COLOR)
        inner_pad.pack(fill="x", padx=16, pady=12)
        tk.Label(
            inner_pad, text=title, bg=CARD_COLOR, fg=TEXT_COLOR,
            font=(FONT_NAME, 12, "bold")
        ).pack(anchor="w")
        return card, inner_pad

    def _radio_card(self, parent, title, subtitle, mode_value, side):
        frame = tk.Frame(parent, bg="#33354a", cursor="hand2")
        frame.pack(side=side, fill="both", expand=True,
                   padx=(0, 6) if side == "left" else (6, 0))

        inner = tk.Frame(frame, bg="#33354a")
        inner.pack(fill="both", expand=True, padx=14, pady=14)

        title_lbl = tk.Label(inner, text=title, bg="#33354a", fg=TEXT_COLOR,
                              font=(FONT_NAME, 12, "bold"), anchor="w")
        title_lbl.pack(anchor="w")
        sub_lbl = tk.Label(inner, text=subtitle, bg="#33354a", fg=SUBTEXT_COLOR,
                            font=(FONT_NAME, 9), anchor="w", wraplength=190, justify="left")
        sub_lbl.pack(anchor="w", pady=(4, 0))

        widgets = [frame, inner, title_lbl, sub_lbl]
        for w in widgets:
            w.bind("<Button-1>", lambda e, m=mode_value: self._select_mode(m))

        frame._title_lbl = title_lbl
        frame._sub_lbl = sub_lbl
        frame._mode = mode_value
        return frame

    def _checkbox(self, parent, text, var):
        cb = tk.Checkbutton(
            parent, text=text, variable=var, bg=CARD_COLOR, fg=TEXT_COLOR,
            selectcolor="#33354a", activebackground=CARD_COLOR, activeforeground=TEXT_COLOR,
            font=(FONT_NAME, 10), anchor="w", relief="flat",
            highlightthickness=0, bd=0, cursor="hand2"
        )
        cb.pack(fill="x", anchor="w", pady=2)
        return cb

    def _select_mode(self, mode):
        self.connection_mode.set(mode)
        for frame, active in [(self.usb_btn, mode == "usb"), (self.wifi_btn, mode == "wifi")]:
            bg = ACCENT if active else "#33354a"
            frame.configure(bg=bg)
            for child in frame.winfo_children():
                child.configure(bg=bg)
            frame._title_lbl.configure(bg=bg, fg="white" if active else TEXT_COLOR)
            frame._sub_lbl.configure(bg=bg, fg="#e3e1ff" if active else SUBTEXT_COLOR)

        if mode == "wifi":
            self.ip_card_outer.pack(fill="x", padx=28, pady=7, after=self.connection_cards_frame)
        else:
            self.ip_card_outer.pack_forget()

    # ---------- Asosiy mantiq ----------
    def set_status(self, text, color=SUBTEXT_COLOR):
        self.status_text.set(text)
        self.status_label.configure(fg=color)

    def on_connect_clicked(self):
        if not os.path.isfile(SCRCPY_EXE):
            self.set_status(
                "Scrcpy hali yuklab olinmoqda yoki internetga ulanish muammosi bor. "
                "Bir oz kutib, qaytadan urinib ko'ring.", ERROR_COLOR)
            return

        self.connect_btn.configure(state="disabled", text="⏳  Ulanmoqda...")
        self.set_status("Ulanmoqda, biroz kuting...", SUBTEXT_COLOR)

        mode = self.connection_mode.get()
        threading.Thread(target=self._connect_worker, args=(mode,), daemon=True).start()

    def _connect_worker(self, mode):
        try:
            if mode == "usb":
                self._connect_usb()
            else:
                self._connect_wifi()
        finally:
            self.root.after(0, lambda: self.connect_btn.configure(state="normal", text="🚀  ULASH"))

    def _connect_usb(self):
        self.root.after(0, lambda: self.set_status("USB qurilmalar tekshirilmoqda...", SUBTEXT_COLOR))
        code, out, err = run_hidden([ADB_EXE, "devices"])
        if code != 0:
            self.root.after(0, lambda: self.set_status(
                f"ADB ishga tushmadi: {err or out}", ERROR_COLOR))
            return

        lines = [l.strip() for l in out.splitlines() if l.strip() and "List of devices" not in l]
        devices = [l for l in lines if l.endswith("device")]
        unauthorized = [l for l in lines if "unauthorized" in l]

        if unauthorized:
            self.root.after(0, lambda: self.set_status(
                "Telefon ekraniga qarang va 'USB orqali debugging'ga RUXSAT bering, "
                "so'ng qaytadan urinib ko'ring.", ERROR_COLOR))
            return

        if not devices:
            self.root.after(0, lambda: self.set_status(
                "Hech qanday qurilma topilmadi.\n"
                "Tekshiring: 1) USB kabel ulanganmi  2) Telefonda 'Dasturchi rejimi' "
                "va 'USB debugging' yoqilganmi  3) Kompyuterga ishonish ('Allow')ni bosganmisiz.",
                ERROR_COLOR))
            return

        self.root.after(0, lambda: self.set_status(
            "Qurilma topildi ✓  Scrcpy ishga tushmoqda...", SUCCESS_COLOR))
        self._launch_scrcpy()

    def _connect_wifi(self):
        ip_raw = self.ip_value.get().strip()
        addr = is_valid_ip_port(ip_raw)
        if not addr:
            self.root.after(0, lambda: self.set_status(
                "IP manzil noto'g'ri. Masalan: 192.168.1.25 yoki 192.168.1.25:5555",
                ERROR_COLOR))
            return

        self.root.after(0, lambda: self.set_status(f"{addr} ga ulanmoqda...", SUBTEXT_COLOR))
        code, out, err = run_hidden([ADB_EXE, "connect", addr], timeout=12)
        full_out = (out + " " + err).lower()

        if "connected" in full_out or "already connected" in full_out:
            self.root.after(0, lambda: self.set_status(
                f"Wi-Fi orqali ulandi ✓ ({addr})  Scrcpy ishga tushmoqda...", SUCCESS_COLOR))
            self._launch_scrcpy()
        else:
            self.root.after(0, lambda: self.set_status(
                f"Ulanmadi: {out or err}\n\n"
                "Tekshiring: 1) Telefon va kompyuter bir xil Wi-Fi tarmoqdami  "
                "2) Telefonda 'Wireless debugging' yoqilganmi  3) IP manzil to'g'rimi.",
                ERROR_COLOR))

    def _launch_scrcpy(self):
        cmd = [SCRCPY_EXE]
        if self.extra_flags["stay_awake"].get():
            cmd.append("--stay-awake")
        if self.extra_flags["fullscreen"].get():
            cmd.append("--fullscreen")
        if self.extra_flags["always_top"].get():
            cmd.append("--always-on-top")
        if self.extra_flags["show_touches"].get():
            cmd.append("--show-touches")

        try:
            launch_detached(cmd, cwd=SCRCPY_DIR)
            self.root.after(0, lambda: self.set_status(
                "Scrcpy oynasi ochildi. Agar ko'rinmasa, vazifalar panelini tekshiring.",
                SUCCESS_COLOR))
        except Exception as e:
            self.root.after(0, lambda: self.set_status(f"Scrcpy ishga tushmadi: {e}", ERROR_COLOR))


# =========================================================
# IOS TAB (AirPlay - uxplay-windows)
# =========================================================
class IOSTab:
    def __init__(self, parent, root):
        self.parent = parent
        self.root = root
        self.status_text = tk.StringVar(value="Tayyor. AirPlay qabul qilishni boshlash uchun tugmani bosing.")
        self.is_running = False
        self.airplay_exe = AIRPLAY_EXE  # boshlang'ich qiymat, topilsa yangilanadi

        self._build_ui()

        # Ilova ochilganda mavjudligini tekshiramiz, lekin avtomatik yuklamaymiz -
        # foydalanuvchi "Boshlash" tugmasini bosganda yuklaymiz (chunki bu katta fayl,
        # va ba'zi odamlar faqat Android funksiyasi uchun ilovani ishlatishlari mumkin).
        self._refresh_running_state()

    def _build_ui(self):
        p = self.parent
        header = tk.Frame(p, bg=BG_COLOR)
        header.pack(fill="x", padx=28, pady=(20, 10))

        tk.Label(
            header, text="🍎 AirPlay Ulagich", bg=BG_COLOR, fg=TEXT_COLOR,
            font=(FONT_NAME, 20, "bold")
        ).pack(anchor="w")
        tk.Label(
            header, text="iPhone/iPad ekranini kompyuterda ko'rish (AirPlay)",
            bg=BG_COLOR, fg=SUBTEXT_COLOR, font=(FONT_NAME, 10)
        ).pack(anchor="w", pady=(2, 0))

        # ---- Info karta ----
        info_card, info_inner = self._make_card(p, "Qanday ishlaydi")
        steps = [
            "1. Pastdagi katta tugmani bosib, AirPlay qabul qilishni yoqing",
            "2. iPhone/iPad'ni shu kompyuter bilan BIR XIL Wi-Fi tarmoqqa ulang",
            f"3. iPhone/iPad'da: Control Center → Screen Mirroring → \"{get_pc_hostname()}\" ni tanlang",
            "4. Ekran avtomatik shu yerda ko'rinadi",
        ]
        for s in steps:
            tk.Label(
                info_inner, text=s, bg=CARD_COLOR, fg=SUBTEXT_COLOR,
                font=(FONT_NAME, 10), anchor="w", justify="left", wraplength=520
            ).pack(anchor="w", pady=(4, 0))

        # ---- Holat kartasi ----
        _, status_card = self._make_card(p, "Holat")
        self.state_label = tk.Label(
            status_card, text="⚪  To'xtatilgan", bg=CARD_COLOR, fg=SUBTEXT_COLOR,
            font=(FONT_NAME, 13, "bold")
        )
        self.state_label.pack(anchor="w", pady=(6, 0))

        # ---- Asosiy tugma ----
        self.toggle_btn = tk.Button(
            p, text="📡  AIRPLAY QABUL QILISHNI BOSHLASH",
            command=self.on_toggle_clicked,
            bg=ACCENT_IOS, fg="white", activebackground="#5fb0ff",
            font=(FONT_NAME, 13, "bold"), relief="flat", cursor="hand2",
            padx=20, pady=12
        )
        self.toggle_btn.pack(fill="x", padx=28, pady=(14, 6))

        self.status_label = tk.Label(
            p, textvariable=self.status_text, bg=BG_COLOR, fg=SUBTEXT_COLOR,
            font=(FONT_NAME, 10), wraplength=540, justify="left"
        )
        self.status_label.pack(fill="x", padx=28, pady=(0, 8))

        # ---- Eslatma ----
        note_card, note_inner = self._make_card(p, "Eslatma")
        tk.Label(
            note_inner,
            text=(
                "Bu funksiya ochiq-kodli \"uxplay-windows\" dasturidan foydalanadi "
                "(Apple'ning rasmiy AirPlay'i emas, lekin shunga o'xshash ishlaydi). "
                "Birinchi marta ishga tushirilganda kerakli dasturni internetdan "
                "yuklab oladi (~60-70 MB) va o'rnatadi. O'rnatish jarayonida Windows "
                "administrator ruxsatini so'rashi mumkin - bu normal, chunki tarmoq "
                "xizmati (Bonjour/mDNS) o'rnatiladi."
            ),
            bg=CARD_COLOR, fg=SUBTEXT_COLOR, font=(FONT_NAME, 9),
            anchor="w", justify="left", wraplength=520
        ).pack(anchor="w")

    def _make_card(self, parent, title):
        card = tk.Frame(parent, bg=CARD_COLOR)
        card.pack(fill="x", padx=28, pady=7)
        inner_pad = tk.Frame(card, bg=CARD_COLOR)
        inner_pad.pack(fill="x", padx=16, pady=12)
        tk.Label(
            inner_pad, text=title, bg=CARD_COLOR, fg=TEXT_COLOR,
            font=(FONT_NAME, 12, "bold")
        ).pack(anchor="w")
        return card, inner_pad

    def set_status(self, text, color=SUBTEXT_COLOR):
        self.status_text.set(text)
        self.status_label.configure(fg=color)

    def _set_running_visual(self, running):
        self.is_running = running
        if running:
            self.state_label.configure(text="🟢  Ishlamoqda - qurilma kutilmoqda", fg=SUCCESS_COLOR)
            self.toggle_btn.configure(text="⏹  AIRPLAY'NI TO'XTATISH", bg=ERROR_COLOR, activebackground="#f07a7a")
        else:
            self.state_label.configure(text="⚪  To'xtatilgan", fg=SUBTEXT_COLOR)
            self.toggle_btn.configure(text="📡  AIRPLAY QABUL QILISHNI BOSHLASH", bg=ACCENT_IOS, activebackground="#5fb0ff")

    def _refresh_running_state(self):
        running = is_process_running("uxplay-windows.exe") or is_process_running("uxplay.exe")
        self._set_running_visual(running)

    def on_toggle_clicked(self):
        if self.is_running:
            self._stop_airplay()
            return

        if not os.path.isfile(self.airplay_exe):
            self.toggle_btn.configure(state="disabled")
            threading.Thread(target=self._install_then_start, daemon=True).start()
        else:
            self.toggle_btn.configure(state="disabled")
            threading.Thread(target=self._start_airplay, daemon=True).start()

    # ---------- O'rnatish ----------
    def _install_then_start(self):
        try:
            self.root.after(0, lambda: self.set_status(
                "Birinchi marta ishga tushirilmoqda: AirPlay dasturi tekshirilmoqda...",
                SUBTEXT_COLOR))

            # Avval winget orqali o'rnatishga harakat qilamiz - bu eng ishonchli yo'l,
            # chunki winget turli installer formatlarini (msi/exe) avtomatik to'g'ri
            # ishga tushiradi va dasturni Windows'ning standart joyiga o'rnatadi.
            if self._winget_available():
                self.root.after(0, lambda: self.set_status(
                    "AirPlay dasturi winget orqali o'rnatilmoqda (Windows oynasida "
                    "ko'rsatmalarni bajaring, administrator ruxsati so'ralishi mumkin)...",
                    SUBTEXT_COLOR))
                ok = self._install_via_winget()
                if ok:
                    found_exe = self._find_installed_exe()
                    if found_exe:
                        self.airplay_exe = found_exe
                        self.root.after(0, lambda: self.set_status(
                            "O'rnatildi! AirPlay ishga tushirilmoqda...", SUCCESS_COLOR))
                        self._start_airplay()
                        return

            # Winget mavjud bo'lmasa yoki muvaffaqiyatsiz bo'lsa, GitHub'dan
            # to'g'ridan-to'g'ri yuklab olishga harakat qilamiz (zaxira usul).
            self.root.after(0, lambda: self.set_status(
                "Internetdan to'g'ridan-to'g'ri yuklab olinmoqda...", SUBTEXT_COLOR))

            download_url, asset_name = self._get_latest_installer_url()
            if not download_url:
                self.root.after(0, lambda: self.set_status(
                    "AirPlay dasturini avtomatik o'rnatib bo'lmadi. Iltimos, "
                    "https://github.com/leapbtw/uxplay-windows/releases sahifasidan "
                    "qo'lda yuklab oling.", ERROR_COLOR))
                return

            installer_path = os.path.join(APP_DIR, asset_name)

            self.root.after(0, lambda: self.set_status(
                f"Yuklab olinmoqda: {asset_name} ...", SUBTEXT_COLOR))

            def reporthook(block_num, block_size, total_size):
                if total_size > 0:
                    percent = min(100, int(block_num * block_size * 100 / total_size))
                    self.root.after(0, lambda p=percent: self.set_status(
                        f"Yuklab olinmoqda... {p}%", SUBTEXT_COLOR))

            urllib.request.urlretrieve(download_url, installer_path, reporthook)

            self.root.after(0, lambda: self.set_status(
                "O'rnatish boshlanmoqda. Windows oynasida ko'rsatmalarni bajaring "
                "(administrator ruxsati so'ralishi mumkin)...", SUBTEXT_COLOR))

            os.makedirs(AIRPLAY_DIR, exist_ok=True)

            if installer_path.lower().endswith(".msi"):
                subprocess.run(["msiexec", "/i", installer_path], timeout=300)
            else:
                subprocess.run([installer_path], timeout=300)

            if os.path.isfile(installer_path):
                os.remove(installer_path)

            found_exe = self._find_installed_exe()
            if found_exe:
                self.airplay_exe = found_exe
                self.root.after(0, lambda: self.set_status(
                    "O'rnatildi! AirPlay ishga tushirilmoqda...", SUCCESS_COLOR))
                self._start_airplay()
            else:
                self.root.after(0, lambda: self.set_status(
                    "O'rnatish tugadi, lekin dastur topilmadi. Iltimos, ilovani qayta ishga "
                    "tushirib, qaytadan urinib ko'ring.", ERROR_COLOR))
        except subprocess.TimeoutExpired:
            self.root.after(0, lambda: self.set_status(
                "O'rnatish vaqti tugadi. Qaytadan urinib ko'ring.", ERROR_COLOR))
        except Exception as e:
            self.root.after(0, lambda: self.set_status(
                f"Xato: {e}\nInternetni tekshirib qaytadan urinib ko'ring.", ERROR_COLOR))
        finally:
            self.root.after(0, lambda: self.toggle_btn.configure(state="normal"))

    def _winget_available(self):
        code, out, _ = run_hidden(["winget", "--version"], timeout=8)
        return code == 0

    def _install_via_winget(self):
        try:
            result = subprocess.run(
                ["winget", "install", "--id=leapbtw.uxplay", "-e",
                 "--accept-package-agreements", "--accept-source-agreements"],
                timeout=300
            )
            return result.returncode == 0
        except Exception:
            return False

    def _get_latest_installer_url(self):
        """GitHub API orqali eng so'nggi uxplay-windows installer havolasini topadi.
        Loyiha ba'zan .exe, ba'zan .msi formatda installer chiqaradi - shu sababli
        ikkisini ham qidiramiz, lekin arm64/UNTESTED nomli fayllarni o'tkazib yuboramiz.
        Agar API (masalan rate-limit sababli) ishlamasa, taxminiy nomlar bilan
        doimiy "latest/download" havolasini sinab ko'ramiz (GitHub'ning bu havolasi
        har doim eng so'nggi versiyaga yo'naltiradi)."""
        try:
            req = urllib.request.Request(
                AIRPLAY_GITHUB_API,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "ScrcpyConnect"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            assets = data.get("assets", [])

            def is_good_candidate(name):
                lname = name.lower()
                if "arm64" in lname or "untested" in lname or "source" in lname:
                    return False
                return lname.endswith(".exe") or lname.endswith(".msi")

            candidates = [a for a in assets if is_good_candidate(a.get("name", ""))]
            if candidates:
                installer_candidates = [a for a in candidates if "installer" in a.get("name", "").lower()]
                chosen = installer_candidates[0] if installer_candidates else candidates[0]
                return chosen.get("browser_download_url"), chosen.get("name")
        except Exception:
            pass

        # Fallback: API ishlamasa, ma'lum bo'lgan fayl nomlari bilan "latest" havolasini sinaymiz.
        fallback_names = ["uxplaywindows-installer.msi", "uxplay-windows-installer.exe"]
        base = "https://github.com/leapbtw/uxplay-windows/releases/latest/download/"
        for name in fallback_names:
            url = base + name
            try:
                req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "ScrcpyConnect"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        return url, name
            except Exception:
                continue
        return None, None

    def _find_installed_exe(self):
        """O'rnatilgandan keyin uxplay-windows.exe odatda qaerga joylashishini tekshiradi
        (winget, to'g'ridan-to'g'ri installer, yoki portable joylashuvlar)."""
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("PROGRAMFILES", "")
        program_files_x86 = os.environ.get("PROGRAMFILES(X86)", "")

        candidates = [
            os.path.join(local_appdata, "Programs", "uxplay-windows", "uxplay-windows.exe"),
            os.path.join(program_files, "uxplay-windows", "uxplay-windows.exe"),
            os.path.join(program_files_x86, "uxplay-windows", "uxplay-windows.exe"),
        ]
        for c in candidates:
            if c and os.path.isfile(c):
                return c

        # winget paketlari odatda WindowsApps yoki WinGet papkalarida bo'ladi
        winget_roots = [
            os.path.join(local_appdata, "Microsoft", "WinGet", "Packages"),
        ]
        for root_dir in winget_roots:
            if os.path.isdir(root_dir):
                for dirpath, _, files in os.walk(root_dir):
                    for f in files:
                        if f.lower() == "uxplay-windows.exe":
                            return os.path.join(dirpath, f)

        # Topilmasa, Start Menu yorlig'i orqali qidirishga harakat qilamiz
        start_menu_dirs = [
            os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(os.environ.get("PROGRAMDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
        ]
        for start_menu in start_menu_dirs:
            if os.path.isdir(start_menu):
                for root_dir, _, files in os.walk(start_menu):
                    for f in files:
                        if f.lower() == "uxplay-windows.lnk":
                            return os.path.join(root_dir, f)
        return None

    # ---------- Ishga tushirish / to'xtatish ----------
    def _start_airplay(self):
        try:
            self.root.after(0, lambda: self.set_status(
                "AirPlay ishga tushirilmoqda...", SUBTEXT_COLOR))
            launch_detached([self.airplay_exe], cwd=os.path.dirname(self.airplay_exe))
            import time
            time.sleep(2)
            self.root.after(0, self._refresh_running_state)
            self.root.after(0, lambda: self.set_status(
                f"Tayyor! iPhone/iPad'da Control Center → Screen Mirroring → "
                f"\"{get_pc_hostname()}\" ni tanlang.", SUCCESS_COLOR))
        except Exception as e:
            self.root.after(0, lambda: self.set_status(f"Ishga tushmadi: {e}", ERROR_COLOR))
        finally:
            self.root.after(0, lambda: self.toggle_btn.configure(state="normal"))

    def _stop_airplay(self):
        self.toggle_btn.configure(state="disabled")
        self.set_status("To'xtatilmoqda...", SUBTEXT_COLOR)

        def worker():
            kill_process("uxplay-windows.exe")
            kill_process("uxplay.exe")
            import time
            time.sleep(1)
            self.root.after(0, self._refresh_running_state)
            self.root.after(0, lambda: self.set_status(
                "To'xtatildi. Qayta boshlash uchun tugmani bosing.", SUBTEXT_COLOR))
            self.root.after(0, lambda: self.toggle_btn.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
