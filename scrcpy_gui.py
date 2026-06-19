#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scrcpy GUI - Android telefon/planshet ekranini ko'rish uchun oson ilova
Faqat 2 ta savol so'raydi: ulanish usuli (USB/Wi-Fi) va kerak bo'lsa IP manzil.
Kod yozish, terminal ochish kerak emas - hammasi tugmalar orqali.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import sys
import re
import zipfile
import urllib.request

# ====== SOZLAMALAR ======
# Ilova qayerdan ishga tushirilsa (PyInstaller bilan yig'ilgan .exe bo'lsa ham),
# scrcpy fayllari shu ilova bilan bir joyda, "scrcpy-bin" papkasida saqlanadi.
def get_app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

APP_DIR = get_app_dir()
SCRCPY_DIR = os.path.join(APP_DIR, "scrcpy-bin")
SCRCPY_EXE = os.path.join(SCRCPY_DIR, "scrcpy.exe")
ADB_EXE = os.path.join(SCRCPY_DIR, "adb.exe")

SCRCPY_DOWNLOAD_URL = "https://github.com/Genymobile/scrcpy/releases/download/v3.1/scrcpy-win64-v3.1.zip"

BG_COLOR = "#1e1f29"
CARD_COLOR = "#282a3a"
ACCENT = "#6c63ff"
ACCENT_HOVER = "#8077ff"
TEXT_COLOR = "#f1f1f6"
SUBTEXT_COLOR = "#9a9ab0"
SUCCESS_COLOR = "#4caf82"
ERROR_COLOR = "#e15c5c"
FONT_NAME = "Segoe UI"


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
    """Scrcpy oynasini asosiy ilovadan mustaqil (ajratilgan) holda ishga tushiradi."""
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS
        creationflags = subprocess.DETACHED_PROCESS
    subprocess.Popen(
        cmd_list,
        cwd=cwd,
        creationflags=creationflags if os.name == "nt" else 0,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


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


class ScrcpyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Scrcpy Ulanish - Android Ekran")
        self.geometry("560x640")
        self.minsize(560, 640)
        self.configure(bg=BG_COLOR)
        self.resizable(False, False)

        self.connection_mode = tk.StringVar(value="usb")
        self.ip_value = tk.StringVar()
        self.status_text = tk.StringVar(value="Tayyor. Ulanish usulini tanlang.")
        self.extra_flags = {
            "stay_awake": tk.BooleanVar(value=True),
            "fullscreen": tk.BooleanVar(value=False),
            "no_audio_loss": tk.BooleanVar(value=False),
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
        """Agar scrcpy-bin papkasi yo'q bo'lsa, birinchi ishga tushirishda
        avtomatik ravishda rasmiy GitHub'dan yuklab oladi va ochadi."""
        if os.path.isfile(SCRCPY_EXE) and os.path.isfile(ADB_EXE):
            return
        # Asosiy oyna hali tayyor bo'lmagani uchun, UI qurilgandan keyin
        # yuklab olish jarayonini boshlash uchun flag qo'yamiz.
        self._needs_download = True

    def _download_scrcpy(self):
        """Scrcpy va adb'ni fonda yuklab oladi, progress statusini ko'rsatadi."""
        zip_path = os.path.join(APP_DIR, "_scrcpy_temp.zip")
        try:
            self.after(0, lambda: self.set_status(
                "Birinchi marta ishga tushirilmoqda: scrcpy yuklab olinmoqda (~25 MB)...",
                SUBTEXT_COLOR))
            self.after(0, lambda: self.connect_btn.configure(state="disabled"))

            os.makedirs(SCRCPY_DIR, exist_ok=True)

            def reporthook(block_num, block_size, total_size):
                if total_size > 0:
                    percent = min(100, int(block_num * block_size * 100 / total_size))
                    self.after(0, lambda p=percent: self.set_status(
                        f"Yuklab olinmoqda... {p}%", SUBTEXT_COLOR))

            urllib.request.urlretrieve(SCRCPY_DOWNLOAD_URL, zip_path, reporthook)

            self.after(0, lambda: self.set_status("Ochib joylashtirilmoqda...", SUBTEXT_COLOR))
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
                self.after(0, lambda: self.set_status(
                    "Tayyor! Endi ulanish usulini tanlab, ULASH tugmasini bosing.",
                    SUCCESS_COLOR))
            else:
                self.after(0, lambda: self.set_status(
                    "Yuklab olindi, lekin scrcpy.exe topilmadi. Internetni tekshirib qaytadan urinib ko'ring.",
                    ERROR_COLOR))
        except Exception as e:
            self.after(0, lambda: self.set_status(
                f"Yuklab olishda xato: {e}\nInternetni tekshirib, ilovani qayta ishga tushiring.",
                ERROR_COLOR))
        finally:
            self.after(0, lambda: self.connect_btn.configure(state="normal"))

    # ---------- UI qurish ----------
    def _build_ui(self):
        header = tk.Frame(self, bg=BG_COLOR)
        header.pack(fill="x", padx=28, pady=(28, 10))

        tk.Label(
            header, text="📱 Scrcpy Ulagich", bg=BG_COLOR, fg=TEXT_COLOR,
            font=(FONT_NAME, 22, "bold")
        ).pack(anchor="w")
        tk.Label(
            header, text="Android telefon/planshet ekranini kompyuterda ko'rish",
            bg=BG_COLOR, fg=SUBTEXT_COLOR, font=(FONT_NAME, 11)
        ).pack(anchor="w", pady=(2, 0))

        # ---- 1-savol: Ulanish usuli ----
        self.connection_cards_frame, card1 = self._make_card("1-qadam: Ulanish usulini tanlang")
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

        # ---- 2-savol: IP manzil (faqat Wi-Fi tanlanganda ko'rinadi) ----
        self.ip_card_outer, self.ip_card_inner = self._make_card("2-qadam: Telefon IP manzili")

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

        pair_btn = tk.Button(
            ip_row, text="Topish", command=self.find_wifi_devices,
            bg="#3a3c52", fg=TEXT_COLOR, activebackground="#4a4d68",
            relief="flat", font=(FONT_NAME, 10), cursor="hand2", padx=10
        )
        pair_btn.pack(side="left")

        # boshida yashirilgan - faqat wifi tanlanganda chiqadi
        self.ip_card_outer.pack_forget()

        # ---- Qo'shimcha sozlamalar (oddiy checkboxlar) ----
        _, card3 = self._make_card("Qo'shimcha sozlamalar (ixtiyoriy)")
        opts = tk.Frame(card3, bg=CARD_COLOR)
        opts.pack(fill="x", pady=(4, 0))

        self._checkbox(opts, "Ekran o'chmasin (uyg'oq turish)", self.extra_flags["stay_awake"])
        self._checkbox(opts, "To'liq ekran rejimida ochish", self.extra_flags["fullscreen"])
        self._checkbox(opts, "Doim ustda turish", self.extra_flags["always_top"])
        self._checkbox(opts, "Ekranda tegishlarni ko'rsatish", self.extra_flags["show_touches"])

        # ---- Ulanish tugmasi ----
        self.connect_btn = tk.Button(
            self, text="🚀  ULASH",
            command=self.on_connect_clicked,
            bg=ACCENT, fg="white", activebackground=ACCENT_HOVER,
            font=(FONT_NAME, 14, "bold"), relief="flat", cursor="hand2",
            padx=20, pady=12
        )
        self.connect_btn.pack(fill="x", padx=28, pady=(14, 6))

        # ---- Status satri ----
        self.status_label = tk.Label(
            self, textvariable=self.status_text, bg=BG_COLOR, fg=SUBTEXT_COLOR,
            font=(FONT_NAME, 10), wraplength=500, justify="left"
        )
        self.status_label.pack(fill="x", padx=28, pady=(0, 14))

        self._select_mode("usb")  # boshlang'ich holat

    def _make_card(self, title):
        card = tk.Frame(self, bg=CARD_COLOR)
        card.pack(fill="x", padx=28, pady=8)
        inner_pad = tk.Frame(card, bg=CARD_COLOR)
        inner_pad.pack(fill="x", padx=16, pady=14)
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
            self.ip_card_outer.pack(fill="x", padx=28, pady=8, after=self.connection_cards_frame)
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
        thread = threading.Thread(target=self._connect_worker, args=(mode,), daemon=True)
        thread.start()

    def _connect_worker(self, mode):
        try:
            if mode == "usb":
                self._connect_usb()
            else:
                self._connect_wifi()
        finally:
            self.after(0, lambda: self.connect_btn.configure(state="normal", text="🚀  ULASH"))

    def _connect_usb(self):
        self.after(0, lambda: self.set_status("USB qurilmalar tekshirilmoqda...", SUBTEXT_COLOR))
        code, out, err = run_hidden([ADB_EXE, "devices"])
        if code != 0:
            self.after(0, lambda: self.set_status(
                f"ADB ishga tushmadi: {err or out}", ERROR_COLOR))
            return

        lines = [l.strip() for l in out.splitlines() if l.strip() and "List of devices" not in l]
        devices = [l for l in lines if l.endswith("device")]
        unauthorized = [l for l in lines if "unauthorized" in l]

        if unauthorized:
            self.after(0, lambda: self.set_status(
                "Telefon ekraniga qarang va 'USB orqali debugging'ga RUXSAT bering, "
                "so'ng qaytadan urinib ko'ring.", ERROR_COLOR))
            return

        if not devices:
            self.after(0, lambda: self.set_status(
                "Hech qanday qurilma topilmadi.\n"
                "Tekshiring: 1) USB kabel ulanganmi  2) Telefonda 'Dasturchi rejimi' "
                "va 'USB debugging' yoqilganmi  3) Kompyuterga ishonish ('Allow')ni bosganmisiz.",
                ERROR_COLOR))
            return

        self.after(0, lambda: self.set_status(
            f"Qurilma topildi ✓  Scrcpy ishga tushmoqda...", SUCCESS_COLOR))
        self._launch_scrcpy()

    def _connect_wifi(self):
        ip_raw = self.ip_value.get().strip()
        addr = is_valid_ip_port(ip_raw)
        if not addr:
            self.after(0, lambda: self.set_status(
                "IP manzil noto'g'ri. Masalan: 192.168.1.25 yoki 192.168.1.25:5555",
                ERROR_COLOR))
            return

        self.after(0, lambda: self.set_status(f"{addr} ga ulanmoqda...", SUBTEXT_COLOR))
        code, out, err = run_hidden([ADB_EXE, "connect", addr], timeout=12)
        full_out = (out + " " + err).lower()

        if "connected" in full_out or "already connected" in full_out:
            self.after(0, lambda: self.set_status(
                f"Wi-Fi orqali ulandi ✓ ({addr})  Scrcpy ishga tushmoqda...", SUCCESS_COLOR))
            self._launch_scrcpy()
        else:
            self.after(0, lambda: self.set_status(
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
            self.after(0, lambda: self.set_status(
                "Scrcpy oynasi ochildi. Agar ko'rinmasa, vazifalar panelini tekshiring.",
                SUCCESS_COLOR))
        except Exception as e:
            self.after(0, lambda: self.set_status(f"Scrcpy ishga tushmadi: {e}", ERROR_COLOR))

    def find_wifi_devices(self):
        """ADB orqali tarmoqdagi mumkin bo'lgan qurilmalarni qidirishga urinish (oddiy yordam)."""
        self.set_status("ADB orqali qurilmalar ro'yxati tekshirilmoqda...", SUBTEXT_COLOR)

        def worker():
            code, out, err = run_hidden([ADB_EXE, "devices", "-l"])
            if code == 0 and out.strip():
                self.after(0, lambda: self.set_status(
                    "Maslahat: telefon Sozlamalar > Wi-Fi > ulangan tarmoq nomini bosib "
                    "IP manzilini ko'rishingiz mumkin. ADB javobi konsolga yozildi emas, "
                    "to'g'ridan-to'g'ri IP manzilni qo'lda kiriting.", SUBTEXT_COLOR))
            else:
                self.after(0, lambda: self.set_status(
                    "Avtomatik qidirish ishlamadi. IP manzilni qo'lda kiriting.", SUBTEXT_COLOR))

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = ScrcpyApp()
    app.mainloop()
