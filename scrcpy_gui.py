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
        self.geometry("600x820")
        self.minsize(400, 400)  # kichraytirish mumkin (Telegram/Chrome kabi)
        self.configure(bg=BG_COLOR)
        self.resizable(True, True)  # erkin kattalashtirish/kichraytirish

        self._set_app_icon()
        self._build_tabs()

        # F11 - to'liq ekran (fullscreen) almashtirish, Esc - chiqish
        self._is_fullscreen = False
        self.bind("<F11>", self._toggle_fullscreen)
        self.bind("<Escape>", self._exit_fullscreen)

    def _toggle_fullscreen(self, event=None):
        self._is_fullscreen = not self._is_fullscreen
        self.attributes("-fullscreen", self._is_fullscreen)
        return "break"

    def _exit_fullscreen(self, event=None):
        if self._is_fullscreen:
            self._is_fullscreen = False
            self.attributes("-fullscreen", False)
        return "break"

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

        # Scrollbar stilini qoramtir mavzuga moslaymiz
        style.configure(
            "Vertical.TScrollbar",
            background=CARD_COLOR, troughcolor=BG_COLOR,
            bordercolor=BG_COLOR, arrowcolor=SUBTEXT_COLOR,
            relief="flat"
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

        android_outer = tk.Frame(notebook, bg=BG_COLOR)
        ios_outer = tk.Frame(notebook, bg=BG_COLOR)

        notebook.add(android_outer, text="🤖  Android")
        notebook.add(ios_outer, text="🍎  iPhone / iPad")

        # Har bir tab ichiga scroll qilinadigan frame yaratamiz - shunda oyna
        # kichrayganda kontent sig'masa, scroll orqali ko'rinadi.
        android_frame = self._make_scrollable(android_outer)
        ios_frame = self._make_scrollable(ios_outer)

        self.android_tab = AndroidTab(android_frame, self)
        self.ios_tab = IOSTab(ios_frame, self)

    def _make_scrollable(self, parent):
        """parent ichida vertikal scroll qilinadigan frame yaratadi va qaytaradi.
        Kontent shu qaytarilgan frame'ga joylanadi."""
        canvas = tk.Canvas(parent, bg=BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG_COLOR)

        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_inner_configure(event):
            # Scroll hududini kontent o'lchamiga moslaymiz
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event):
            # Ichki frame kengligini canvas kengligiga tenglashtiramiz
            canvas.itemconfig(inner_id, width=event.width)

        inner.bind("<Configure>", on_inner_configure)
        canvas.bind("<Configure>", on_canvas_configure)

        # Sichqoncha g'ildiragi bilan scroll qilish
        def on_mousewheel(event):
            # Windows va boshqa platformalar uchun
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        def bind_wheel(event):
            canvas.bind_all("<MouseWheel>", on_mousewheel)
            canvas.bind_all("<Button-4>", on_mousewheel)
            canvas.bind_all("<Button-5>", on_mousewheel)

        def unbind_wheel(event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        # Faqat sichqoncha shu canvas ustida bo'lganda g'ildirak ishlasin
        canvas.bind("<Enter>", bind_wheel)
        canvas.bind("<Leave>", unbind_wheel)

        return inner

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
        # Ekran aylanishi: "auto" (erkin aylanadi), yoki qulflangan holatlar
        self.orientation = tk.StringVar(value="auto")

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
            text="Telefonda: Sozlamalar → Wi-Fi → ulangan tarmoq → IP manzil (masalan: 192.168.1.25)",
            bg=CARD_COLOR, fg=SUBTEXT_COLOR, font=(FONT_NAME, 9),
            anchor="w", justify="left", wraplength=520
        ).pack(anchor="w")

        ip_row = tk.Frame(self.ip_card_inner, bg=CARD_COLOR)
        ip_row.pack(fill="x", pady=(8, 0))
        self.ip_entry = tk.Entry(
            ip_row, textvariable=self.ip_value, font=(FONT_NAME, 13),
            bg="#33354a", fg=TEXT_COLOR, insertbackground=TEXT_COLOR,
            relief="flat", width=28
        )
        self.ip_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))

        # Wi-Fi ulanish uchun muhim yo'riqnoma
        tk.Label(
            self.ip_card_inner,
            text=(
                "⚠️  Birinchi marta Wi-Fi orqali ulash uchun:\n"
                "1) Telefonni USB kabel bilan kompyuterga ulang (debugging yoqilgan holda)\n"
                "2) Pastdagi \"USB→Wi-Fi tayyorlash\" tugmasini bosing\n"
                "3) Kabelni uzib, IP manzilni kiritib \"ULASH\" ni bosing\n"
                "(Android 11+ da \"Wireless debugging\" yoqilgan bo'lsa, to'g'ridan-to'g'ri ulanadi)"
            ),
            bg=CARD_COLOR, fg=SUBTEXT_COLOR, font=(FONT_NAME, 8),
            anchor="w", justify="left", wraplength=520
        ).pack(anchor="w", pady=(8, 0))

        # USB→Wi-Fi tayyorlash tugmasi (tcpip rejimini yoqadi)
        self.tcpip_btn = tk.Button(
            self.ip_card_inner, text="🔧  USB→Wi-Fi tayyorlash (kabel ulangan holda)",
            command=self._prepare_wifi_from_usb,
            bg="#3a3c52", fg=TEXT_COLOR, activebackground="#4a4d68",
            relief="flat", font=(FONT_NAME, 9), cursor="hand2", padx=10, pady=6
        )
        self.tcpip_btn.pack(anchor="w", pady=(8, 0))

        self.ip_card_outer.pack_forget()

        _, card3 = self._make_card(p, "Qo'shimcha sozlamalar (ixtiyoriy)")
        opts = tk.Frame(card3, bg=CARD_COLOR)
        opts.pack(fill="x", pady=(4, 0))

        self._checkbox(opts, "Ekran o'chmasin (uyg'oq turish)", self.extra_flags["stay_awake"])
        self._checkbox(opts, "To'liq ekran rejimida ochish", self.extra_flags["fullscreen"])
        self._checkbox(opts, "Doim ustda turish", self.extra_flags["always_top"])
        self._checkbox(opts, "Ekranda tegishlarni ko'rsatish", self.extra_flags["show_touches"])

        # Ekran aylanishi (orientatsiya) tanlovi
        orient_row = tk.Frame(card3, bg=CARD_COLOR)
        orient_row.pack(fill="x", anchor="w", pady=(8, 0))
        tk.Label(
            orient_row, text="🔄  Ekran aylanishi:", bg=CARD_COLOR, fg=TEXT_COLOR,
            font=(FONT_NAME, 10)
        ).pack(side="left", padx=(0, 8))

        for label, value in [("Avtomatik", "auto"), ("Vertikal", "portrait"), ("Gorizontal", "landscape")]:
            rb = tk.Radiobutton(
                orient_row, text=label, variable=self.orientation, value=value,
                bg=CARD_COLOR, fg=TEXT_COLOR, selectcolor="#33354a",
                activebackground=CARD_COLOR, activeforeground=TEXT_COLOR,
                font=(FONT_NAME, 9), relief="flat", highlightthickness=0,
                bd=0, cursor="hand2"
            )
            rb.pack(side="left", padx=(0, 6))

        tk.Label(
            card3,
            text="ℹ️  \"Avtomatik\" — planshet aylanganda ekran ham aylanadi. "
                 "Agar aylanishda kadr buzilsa, \"Vertikal\" yoki \"Gorizontal\" ni tanlab qulflang.",
            bg=CARD_COLOR, fg=SUBTEXT_COLOR, font=(FONT_NAME, 8),
            anchor="w", justify="left", wraplength=520
        ).pack(anchor="w", pady=(6, 0))

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

        # Qurilma serialini ajratib olamiz. USB qurilma odatda IP:PORT formatida
        # EMAS (oddiy seriya raqami). Agar bir nechta qurilma bo'lsa (masalan
        # eski Wi-Fi ulanish qolgan bo'lsa), USB qurilmani tanlaymiz.
        usb_serials = [l.split()[0] for l in devices if ":" not in l.split()[0]]
        serial = usb_serials[0] if usb_serials else devices[0].split()[0]

        self.root.after(0, lambda: self.set_status(
            "Qurilma topildi ✓  Scrcpy ishga tushmoqda...", SUCCESS_COLOR))
        self._launch_scrcpy(serial=serial)

    def _prepare_wifi_from_usb(self):
        """USB orqali ulangan telefonni Wi-Fi (tcpip) rejimiga o'tkazadi va
        IP manzilini avtomatik aniqlab, maydonga yozadi."""
        self.tcpip_btn.configure(state="disabled")
        self.set_status("USB qurilma tekshirilmoqda...", SUBTEXT_COLOR)
        threading.Thread(target=self._prepare_wifi_worker, daemon=True).start()

    def _prepare_wifi_worker(self):
        try:
            run_hidden([ADB_EXE, "start-server"], timeout=10)
            # USB qurilma bor-yo'qligini tekshiramiz
            code, out, err = run_hidden([ADB_EXE, "devices"], timeout=10)
            lines = [l.strip() for l in out.splitlines()
                     if l.strip() and "List of devices" not in l]
            usb_devices = [l.split()[0] for l in lines
                           if l.endswith("device") and ":" not in l.split()[0]]

            if not usb_devices:
                self.root.after(0, lambda: self.set_status(
                    "USB qurilma topilmadi. Avval telefonni USB kabel bilan ulang "
                    "(USB debugging yoqilgan va 'Allow' bosilgan bo'lsin).", ERROR_COLOR))
                return

            usb_serial = usb_devices[0]

            # IP manzilni telefonning o'zidan aniqlaymiz
            self.root.after(0, lambda: self.set_status(
                "Telefon IP manzili aniqlanmoqda...", SUBTEXT_COLOR))
            ip = self._detect_device_ip(usb_serial)

            # tcpip rejimini yoqamiz (5555 port)
            self.root.after(0, lambda: self.set_status(
                "Wi-Fi rejimi yoqilmoqda...", SUBTEXT_COLOR))
            run_hidden([ADB_EXE, "-s", usb_serial, "tcpip", "5555"], timeout=12)
            import time
            time.sleep(2)

            if ip:
                # IP ni maydonga yozamiz
                self.root.after(0, lambda: self.ip_value.set(ip))
                self.root.after(0, lambda: self.set_status(
                    f"Tayyor! IP manzil aniqlandi: {ip}\n"
                    "Endi USB kabelni uzib, \"🚀 ULASH\" tugmasini bosing.",
                    SUCCESS_COLOR))
            else:
                self.root.after(0, lambda: self.set_status(
                    "Wi-Fi rejimi yoqildi, lekin IP manzilni avtomatik aniqlab bo'lmadi.\n"
                    "Telefon Sozlamalar → Wi-Fi dan IP manzilni qo'lda kiriting, "
                    "USB kabelni uzib, \"🚀 ULASH\" ni bosing.", SUBTEXT_COLOR))
        except Exception as e:
            self.root.after(0, lambda: self.set_status(f"Xato: {e}", ERROR_COLOR))
        finally:
            self.root.after(0, lambda: self.tcpip_btn.configure(state="normal"))

    def _detect_device_ip(self, serial):
        """Telefonning Wi-Fi IP manzilini adb orqali aniqlaydi."""
        # Usul 1: ip route orqali (eng ishonchli)
        code, out, err = run_hidden(
            [ADB_EXE, "-s", serial, "shell", "ip", "route"], timeout=10)
        for line in out.splitlines():
            # masalan: "192.168.1.0/24 dev wlan0 ... src 192.168.1.25"
            if "wlan" in line and "src" in line:
                parts = line.split()
                if "src" in parts:
                    idx = parts.index("src")
                    if idx + 1 < len(parts):
                        return parts[idx + 1]

        # Usul 2: ifconfig wlan0 orqali
        code, out, err = run_hidden(
            [ADB_EXE, "-s", serial, "shell", "ifconfig", "wlan0"], timeout=10)
        m = re.search(r"inet addr:(\d+\.\d+\.\d+\.\d+)", out)
        if m:
            return m.group(1)
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out)
        if m:
            return m.group(1)

        return None

    def _connect_wifi(self):
        ip_raw = self.ip_value.get().strip()
        addr = is_valid_ip_port(ip_raw)
        if not addr:
            self.root.after(0, lambda: self.set_status(
                "IP manzil noto'g'ri. Masalan: 192.168.1.25 yoki 192.168.1.25:5555",
                ERROR_COLOR))
            return

        # 1) ADB serverini ishga tushiramiz (birinchi ulanishda kerak bo'ladi)
        self.root.after(0, lambda: self.set_status("ADB tayyorlanmoqda...", SUBTEXT_COLOR))
        run_hidden([ADB_EXE, "start-server"], timeout=10)

        # 2) Ulanamiz. Ba'zida birinchi urinish "offline" bo'ladi, shuning uchun
        #    2 marta urinib ko'ramiz.
        self.root.after(0, lambda: self.set_status(f"{addr} ga ulanmoqda...", SUBTEXT_COLOR))
        connected = False
        last_output = ""
        for attempt in range(2):
            code, out, err = run_hidden([ADB_EXE, "connect", addr], timeout=12)
            last_output = (out + " " + err).strip()
            full_out = last_output.lower()
            if "connected" in full_out and "cannot" not in full_out and "failed" not in full_out:
                connected = True
                break
            import time
            time.sleep(1.5)

        if not connected:
            self.root.after(0, lambda: self.set_status(
                f"Ulanmadi: {last_output}\n\n"
                "Tekshiring:\n"
                "1) Telefon va kompyuter BIR XIL Wi-Fi tarmoqda ekanligini\n"
                "2) Telefonda 'Wireless debugging' (yoki 'USB debugging') yoqilganligini\n"
                "3) IP manzil to'g'riligini\n\n"
                "Eslatma: Yangi Android (11+) da avval telefonni USB orqali bir marta "
                "ulab, pastdagi maslahatni o'qing.",
                ERROR_COLOR))
            return

        # 3) Ulanish muvaffaqiyatli - qurilma haqiqatan 'device' holatida ekanligini tekshiramiz
        import time
        time.sleep(1)
        code, out, err = run_hidden([ADB_EXE, "devices"], timeout=10)
        device_online = False
        for line in out.splitlines():
            line = line.strip()
            if addr in line and line.endswith("device"):
                device_online = True
                break

        if not device_online:
            # "offline" bo'lsa, bir marta qayta ulanishga harakat qilamiz
            run_hidden([ADB_EXE, "disconnect", addr], timeout=8)
            time.sleep(1)
            run_hidden([ADB_EXE, "connect", addr], timeout=12)
            time.sleep(1.5)

        self.root.after(0, lambda: self.set_status(
            f"Wi-Fi orqali ulandi ✓ ({addr})  Scrcpy ishga tushmoqda...", SUCCESS_COLOR))
        # Scrcpy ga ANIQ shu qurilmani ko'rsatamiz (-s bilan), aks holda u
        # boshqa qurilmaga ulanishi yoki chalkashishi mumkin.
        self._launch_scrcpy(serial=addr)

    def _launch_scrcpy(self, serial=None):
        cmd = [SCRCPY_EXE]
        # Aniq qurilma ko'rsatilgan bo'lsa (Wi-Fi yoki bir nechta qurilma holatida)
        if serial:
            cmd += ["-s", serial]
        if self.extra_flags["stay_awake"].get():
            cmd.append("--stay-awake")
        if self.extra_flags["fullscreen"].get():
            cmd.append("--fullscreen")
        if self.extra_flags["always_top"].get():
            cmd.append("--always-on-top")
        if self.extra_flags["show_touches"].get():
            cmd.append("--show-touches")

        # Ekran aylanishi (orientatsiya)
        # "auto" - hech narsa qo'shmaymiz, scrcpy o'zi aylanishni boshqaradi (unlocked).
        # "portrait"/"landscape" - video orientatsiyani qulflaymiz, shunda aylanганда
        # kadr buzilmaydi (qulflangan holatda qoladi).
        orient = self.orientation.get()
        if orient == "portrait":
            cmd += ["--lock-video-orientation=0"]
        elif orient == "landscape":
            cmd += ["--lock-video-orientation=3"]

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

        # Sozlamalar (lagni boshqarish uchun)
        self.audio_on = tk.BooleanVar(value=False)      # ovoz: boshida o'chiq (lag kam bo'lsin)
        self.low_lag = tk.BooleanVar(value=True)        # past lag rejimi: boshida yoqilgan
        self.quality = tk.StringVar(value="720p")       # sifat: 720p / 1080p / original

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

        # ---- Sozlamalar kartasi (lagni boshqarish) ----
        _, settings_card = self._make_card(p, "Sozlamalar (lagni kamaytirish)")

        # Ovoz
        self._checkbox(
            settings_card, "🔊  Ovozni yoqish (o'chirilsa lag kamayadi)",
            self.audio_on
        )
        # Past lag rejimi
        self._checkbox(
            settings_card, "⚡  Past lag rejimi (tavsiya etiladi)",
            self.low_lag
        )

        # Sifat tanlash
        quality_row = tk.Frame(settings_card, bg=CARD_COLOR)
        quality_row.pack(fill="x", anchor="w", pady=(8, 0))
        tk.Label(
            quality_row, text="📺  Sifat:", bg=CARD_COLOR, fg=TEXT_COLOR,
            font=(FONT_NAME, 10)
        ).pack(side="left", padx=(0, 8))

        for label, value in [("720p (tez)", "720p"), ("1080p (aniq)", "1080p"), ("Original", "original")]:
            rb = tk.Radiobutton(
                quality_row, text=label, variable=self.quality, value=value,
                bg=CARD_COLOR, fg=TEXT_COLOR, selectcolor="#33354a",
                activebackground=CARD_COLOR, activeforeground=TEXT_COLOR,
                font=(FONT_NAME, 9), relief="flat", highlightthickness=0,
                bd=0, cursor="hand2"
            )
            rb.pack(side="left", padx=(0, 6))

        # Sozlama o'zgarganda avtomatik faylga yozish va (ishlab tursa) restart
        self.audio_on.trace_add("write", lambda *a: self._on_settings_changed())
        self.low_lag.trace_add("write", lambda *a: self._on_settings_changed())
        self.quality.trace_add("write", lambda *a: self._on_settings_changed())

        # Kichik eslatma
        tk.Label(
            settings_card,
            text="ℹ️  Sozlama o'zgarganda, iPhone/iPad'da AirPlay'ni qaytadan ulang "
                 "(yangi sozlama shunda qo'llanadi).",
            bg=CARD_COLOR, fg=SUBTEXT_COLOR, font=(FONT_NAME, 8),
            anchor="w", justify="left", wraplength=520
        ).pack(anchor="w", pady=(8, 0))

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

    def _checkbox(self, parent, text, var):
        cb = tk.Checkbutton(
            parent, text=text, variable=var, bg=CARD_COLOR, fg=TEXT_COLOR,
            selectcolor="#33354a", activebackground=CARD_COLOR, activeforeground=TEXT_COLOR,
            font=(FONT_NAME, 10), anchor="w", relief="flat",
            highlightthickness=0, bd=0, cursor="hand2"
        )
        cb.pack(fill="x", anchor="w", pady=2)
        return cb

    def _build_uxplay_args(self):
        """Tanlangan sozlamalarga qarab UxPlay argumentlari ro'yxatini quradi."""
        args = []
        # Ovoz: o'chirilgan bo'lsa -as 0 (audioni butunlay o'chiradi, lagni kamaytiradi)
        if not self.audio_on.get():
            args.append("-as 0")
        # Past lag: video/audio timestamp sinxronizatsiyani o'chiradi
        if self.low_lag.get():
            args.append("-vsync no")
        # Sifat: ekran o'lchamini cheklash (kichikroq = kamroq lag)
        q = self.quality.get()
        if q == "720p":
            args.append("-s 1280x720")
        elif q == "1080p":
            args.append("-s 1920x1080")
        # "original" bo'lsa -s qo'shmaymiz (qurilmaning o'z o'lchamida)
        return " ".join(args)

    def _arguments_file_path(self):
        return os.path.join(
            os.environ.get("APPDATA", APP_DIR), "uxplay-windows", "arguments.txt"
        )

    def _write_arguments_file(self):
        """Sozlamalarni uxplay-windows o'qiydigan arguments.txt fayliga yozadi."""
        try:
            args_str = self._build_uxplay_args()
            path = self._arguments_file_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(args_str)
            return True
        except Exception:
            return False

    def _on_settings_changed(self):
        """Sozlama o'zgarganda - faylga yozamiz va agar ishlab tursa, qayta ishga tushiramiz."""
        self._write_arguments_file()
        if self.is_running:
            self.set_status(
                "Sozlama saqlandi. Qo'llanmoqda — iPhone/iPad'da AirPlay'ni qaytadan "
                "ulashingiz kerak bo'lishi mumkin (Control Center → Screen Mirroring).",
                SUBTEXT_COLOR)
            threading.Thread(target=self._restart_airplay, daemon=True).start()
        else:
            self.set_status(
                "Sozlama saqlandi. AirPlay'ni boshlaganingizda qo'llanadi.",
                SUCCESS_COLOR)

    def _launch_airplay_exe(self):
        """uxplay-windows ni ishga tushiradi. Agar yo'l .lnk yorliq bo'lsa yoki
        oddiy launch ishlamasa, Windows 'start' buyrug'i orqali ochadi."""
        try:
            if self.airplay_exe.lower().endswith(".lnk"):
                # .lnk yorliqni explorer orqali ochamiz
                os.startfile(self.airplay_exe)
            else:
                launch_detached([self.airplay_exe], cwd=os.path.dirname(self.airplay_exe))
        except Exception:
            # Zaxira: os.startfile har qanday holatda ishlashga harakat qiladi
            try:
                os.startfile(self.airplay_exe)
            except Exception:
                pass

    def _restart_airplay(self):
        """AirPlay serverini yangi sozlamalar bilan to'liq qayta ishga tushiradi.
        uxplay-windows tray ilovasi arguments.txt ni faqat o'zi boshlanganda
        o'qiydi, shuning uchun butun jarayonni qayta ishga tushiramiz."""
        # Sozlama faylini yana bir bor yozib qo'yamiz (kafolat uchun)
        self._write_arguments_file()
        kill_process("uxplay-windows.exe")
        kill_process("uxplay.exe")
        import time
        # uxplay-windows to'liq yopilishini kutamiz
        time.sleep(3)
        # Endi qaytadan ishga tushiramiz - u arguments.txt ni qayta o'qiydi
        try:
            self._launch_airplay_exe()
            # uxplay-windows ichki uxplay.exe ni 3 soniyadan keyin ishga tushiradi,
            # shuning uchun biroz ko'proq kutamiz
            time.sleep(5)
            self.root.after(0, self._refresh_running_state)
            self.root.after(0, lambda: self.set_status(
                "Yangi sozlamalar bilan tayyor! iPhone/iPad'da Control Center → "
                f"Screen Mirroring → \"{get_pc_hostname()}\" ni qaytadan tanlang.",
                SUCCESS_COLOR))
        except Exception as e:
            self.root.after(0, lambda: self.set_status(f"Qayta ishga tushmadi: {e}", ERROR_COLOR))

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
            # Avval sozlamalarni faylga yozamiz (lag sozlamalari shu orqali qo'llanadi)
            self._write_arguments_file()

            self.root.after(0, lambda: self.set_status(
                "AirPlay ishga tushirilmoqda...", SUBTEXT_COLOR))
            self._launch_airplay_exe()
            import time
            time.sleep(3)
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
