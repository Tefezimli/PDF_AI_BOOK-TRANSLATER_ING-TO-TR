import os
import re
import sys
import json
import time
import ctypes
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pymupdf as fitz
from PIL import Image, ImageTk
import torch

# Mevcut çeviri motorumuzu hiçbir değişikliğe uğratmadan içeri aktarıyoruz
import pdf_bridge
from core.user_settings import apply_lmstudio_env, load_settings, save_settings

# Windows High-DPI (Bulanık görüntü önleyici, 1080p/2K/4K keskinlik kilidi)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# --- RENK PALETİ (OBSIDIAN CYBER-WORKSTATION) ---
BG_MAIN = "#0B0F19"       # Ana arka plan
BG_PANEL = "#111827"      # Panel yüzeyi
BG_CARD = "#1E293B"       # Bilgi kutuları ve giriş alanları
BG_TERMINAL = "#070A12"   # Konsol ve metin inceleme zemini
BORDER_CLR = "#334155"    # İnce çerçeve çizgisi
ACCENT_BLUE = "#38BDF8"   # Siber Kobalt Mavi
ACCENT_GREEN = "#10B981"  # Zümrüt Yeşili (Başarı / Aktif GPU)
ACCENT_AMBER = "#F59E0B"  # Kehribar Sarısı (CPU / Uyarı)
TEXT_PRIMARY = "#F8FAFC"  # Parlak Beyaz Metin
TEXT_MUTED = "#94A3B8"    # İkincil Gri-Mavi Metin


class StreamInterceptor:
    """pdf_bridge.py çıktılarını yakalar ve ilerleme yüzdesine dönüştürür."""
    def __init__(self, app: "EnterpriseTranslatorStudio"):
        self.app = app
        self.orig_stdout = sys.__stdout__

    def write(self, text: str):
        if self.orig_stdout:
            try:
                self.orig_stdout.write(text)
            except Exception:
                pass
        if text:
            self.app.root.after(0, self.app.process_console_output, text)

    def flush(self):
        if self.orig_stdout:
            try:
                self.orig_stdout.flush()
            except Exception:
                pass


class EnterpriseTranslatorStudio:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PDF AI Engine Pro — Offline Academic Book & Slide Translation Workstation")
        self.root.geometry("1240x780")
        self.root.minsize(1060, 680)
        self.root.configure(bg=BG_MAIN)

        self.input_pdf = tk.StringVar()
        self.output_pdf = tk.StringVar()
        self.status_text = tk.StringVar(value="SİSTEM HAZIR  •  Analiz ve çeviri için kaynak PDF belgesi seçin.")
        self.stage_text = tk.StringVar(value="Beklemede")
        self.timer_text = tk.StringVar(value="00:00")
        self.progress_val = tk.DoubleVar(value=0.0)

        self.is_running = False
        self.start_time = 0.0
        self.total_blocks = 1
        self.preview_doc: fitz.Document = None
        self.preview_page_idx = 0
        self.showing_translated_preview = False
        self.tk_preview_img = None
        # İlerleme kaynağı: motor callback'i ilk olayı gönderince "callback"e döner;
        # o ana kadar konsol çıktısı kazıması (yedek kanal) yüzdeyi günceller.
        self._progress_source = "console"
        self.settings = load_settings()

        self._configure_ttk_styles()
        self._build_layout()
        self._refresh_telemetry_badges()

        # Varsayılan dosya kontrolü
        default_in = os.path.abspath("ornek_belge.pdf")
        if os.path.exists(default_in):
            self._set_input_file(default_in)

        sys.stdout = StreamInterceptor(self)
        sys.stderr = sys.stdout

    def _configure_ttk_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Studio.TNotebook",
            background=BG_PANEL,
            borderwidth=0,
            tabmargins=[2, 4, 2, 0]
        )
        style.configure(
            "Studio.TNotebook.Tab",
            background=BG_CARD,
            foreground=TEXT_MUTED,
            padding=[16, 8],
            font=("Segoe UI Semibold", 9),
            borderwidth=0
        )
        style.map(
            "Studio.TNotebook.Tab",
            background=[("selected", ACCENT_BLUE)],
            foreground=[("selected", "#070A12")]
        )
        style.configure(
            "Cyber.Horizontal.TProgressbar",
            troughcolor=BG_TERMINAL,
            background=ACCENT_BLUE,
            bordercolor=BG_PANEL,
            lightcolor=ACCENT_BLUE,
            darkcolor=ACCENT_BLUE,
            thickness=10
        )

    def _build_layout(self):
        # 1. ÜST BAŞLIK VE CANLI TELEMETRİ PANELİ
        top_bar = tk.Frame(self.root, bg=BG_PANEL, height=74, highlightthickness=1, highlightbackground=BORDER_CLR)
        top_bar.pack(fill=tk.X, side=tk.TOP)
        top_bar.pack_propagate(False)

        brand_frame = tk.Frame(top_bar, bg=BG_PANEL, padx=20)
        brand_frame.pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(
            brand_frame,
            text="⚡ PDF AI ENGINE",
            font=("Segoe UI Black", 15),
            fg=TEXT_PRIMARY,
            bg=BG_PANEL
        ).pack(anchor="w", pady=(12, 0))

        tk.Label(
            brand_frame,
            text="HYBRID C++17 OpenMP & NEURAL DLA WORKSTATION  •  v18.1 MASTER",
            font=("Consolas", 8, "bold"),
            fg=ACCENT_BLUE,
            bg=BG_PANEL
        ).pack(anchor="w")

        # Sağ Üst Telemetri Kartları (Otomatik GPU/CPU Algılama Entegre Edildi)
        badge_container = tk.Frame(top_bar, bg=BG_PANEL, padx=16)
        badge_container.pack(side=tk.RIGHT, fill=tk.Y, pady=12)

        self.badge_offline = self._create_badge(badge_container, "GÜVENLİK PROTOKOLÜ", "🛡️ %100 OFFLINE", ACCENT_GREEN)
        self.badge_hw = self._create_badge(badge_container, "YAPAY ZEKA DONANIMI", "Algılanıyor...", ACCENT_BLUE)
        self.badge_cpp = self._create_badge(badge_container, "MİZANPAJ ÇEKİRDEĞİ", "Kontrol ediliyor...", ACCENT_AMBER)
        self.badge_cache = self._create_badge(badge_container, "ÇEVİRİ ÖNBELLEĞİ", "0 Kalıp Hazır", TEXT_PRIMARY)

        # 2. ANA ÇALIŞMA ALANI
        main_body = tk.Frame(self.root, bg=BG_MAIN, padx=14, pady=12)
        main_body.pack(fill=tk.BOTH, expand=True)

        left_panel = tk.Frame(main_body, bg=BG_PANEL, width=410, highlightthickness=1, highlightbackground=BORDER_CLR)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        left_panel.pack_propagate(False)

        self._build_left_panel(left_panel)

        right_panel = tk.Frame(main_body, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER_CLR)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_right_panel(right_panel)

        # 3. ALT DURUM ÇUBUĞU
        footer = tk.Frame(self.root, bg=BG_PANEL, height=34, highlightthickness=1, highlightbackground=BORDER_CLR)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        tk.Label(
            footer,
            textvariable=self.status_text,
            font=("Segoe UI", 9),
            fg=TEXT_MUTED,
            bg=BG_PANEL,
            padx=16
        ).pack(side=tk.LEFT)

        tk.Label(
            footer,
            text="Zero-Tofu Glif Kalkanı: Aktif  |  Model: Helsinki-NLP/opus-mt-tc-big-en-tr",
            font=("Consolas", 8),
            fg=BORDER_CLR,
            bg=BG_PANEL,
            padx=16
        ).pack(side=tk.RIGHT)

    def _create_badge(self, parent: tk.Widget, title: str, val: str, fg_color: str) -> tk.Label:
        card = tk.Frame(parent, bg=BG_CARD, padx=12, pady=5, highlightthickness=1, highlightbackground=BORDER_CLR)
        card.pack(side=tk.LEFT, padx=5, fill=tk.Y)
        tk.Label(card, text=title, font=("Segoe UI", 7, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(anchor="w")
        lbl = tk.Label(card, text=val, font=("Consolas", 9, "bold"), fg=fg_color, bg=BG_CARD)
        lbl.pack(anchor="w")
        return lbl

    def _build_left_panel(self, parent: tk.Frame):
        sec1 = tk.Frame(parent, bg=BG_PANEL, padx=16, pady=14)
        sec1.pack(fill=tk.X)

        tk.Label(sec1, text="BELGE YAPILANDIRMASI", font=("Segoe UI", 9, "bold"), fg=ACCENT_BLUE, bg=BG_PANEL).pack(anchor="w", pady=(0, 8))

        tk.Label(sec1, text="Kaynak PDF (İngilizce Kitap / Slayt):", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=BG_PANEL).pack(anchor="w")
        in_row = tk.Frame(sec1, bg=BG_PANEL)
        in_row.pack(fill=tk.X, pady=(3, 10))

        tk.Entry(
            in_row, textvariable=self.input_pdf, font=("Consolas", 9),
            bg=BG_CARD, fg=TEXT_PRIMARY, insertbackground="white", relief=tk.FLAT
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 6))

        tk.Button(
            in_row, text="Seç...", command=self._browse_input,
            font=("Segoe UI Semibold", 9), bg=ACCENT_BLUE, fg="#070A12",
            activebackground="#7DD3FC", relief=tk.FLAT, padx=12, pady=4, cursor="hand2"
        ).pack(side=tk.RIGHT)

        tk.Label(sec1, text="Üretilecek Hedef PDF (Türkçe):", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=BG_PANEL).pack(anchor="w")
        out_row = tk.Frame(sec1, bg=BG_PANEL)
        out_row.pack(fill=tk.X, pady=(3, 6))

        tk.Entry(
            out_row, textvariable=self.output_pdf, font=("Consolas", 9),
            bg=BG_CARD, fg=TEXT_PRIMARY, insertbackground="white", relief=tk.FLAT
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 6))

        tk.Button(
            out_row, text="Hedef...", command=self._browse_output,
            font=("Segoe UI Semibold", 9), bg=BG_CARD, fg=TEXT_PRIMARY,
            activebackground=BORDER_CLR, relief=tk.FLAT, padx=10, pady=4, cursor="hand2"
        ).pack(side=tk.RIGHT)

        self.doc_meta_lbl = tk.Label(
            sec1, text="Henüz belge yüklenmedi.", font=("Consolas", 8),
            fg=ACCENT_GREEN, bg=BG_TERMINAL, anchor="w", padx=10, pady=6
        )
        self.doc_meta_lbl.pack(fill=tk.X, pady=(6, 0))

        preview_box = tk.Frame(parent, bg=BG_PANEL, padx=16, pady=4)
        preview_box.pack(fill=tk.BOTH, expand=True)

        hdr_row = tk.Frame(preview_box, bg=BG_PANEL)
        hdr_row.pack(fill=tk.X, pady=(0, 6))

        self.preview_title_lbl = tk.Label(
            hdr_row, text="CANLI SAYFA ÖNİZLEME", font=("Segoe UI", 9, "bold"), fg=ACCENT_BLUE, bg=BG_PANEL
        )
        self.preview_title_lbl.pack(side=tk.LEFT)

        self.toggle_preview_btn = tk.Button(
            hdr_row, text="🔄 Türkçe Çıktıyı Göster", command=self._toggle_preview_source,
            font=("Segoe UI", 8, "bold"), bg=BG_CARD, fg=ACCENT_GREEN,
            relief=tk.FLAT, padx=8, pady=2, state=tk.DISABLED, cursor="hand2"
        )
        self.toggle_preview_btn.pack(side=tk.RIGHT)

        self.canvas_preview = tk.Canvas(
            preview_box, bg=BG_TERMINAL, highlightthickness=1, highlightbackground=BORDER_CLR
        )
        self.canvas_preview.pack(fill=tk.BOTH, expand=True)

        nav_row = tk.Frame(preview_box, bg=BG_PANEL, pady=8)
        nav_row.pack(fill=tk.X)

        tk.Button(
            nav_row, text="◀ Önceki", command=lambda: self._step_preview(-1),
            font=("Segoe UI", 8, "bold"), bg=BG_CARD, fg=TEXT_PRIMARY, relief=tk.FLAT, padx=10, cursor="hand2"
        ).pack(side=tk.LEFT)

        self.page_counter_lbl = tk.Label(nav_row, text="Sayfa: - / -", font=("Consolas", 9, "bold"), fg=TEXT_MUTED, bg=BG_PANEL)
        self.page_counter_lbl.pack(side=tk.LEFT, expand=True)

        tk.Button(
            nav_row, text="Sonraki ▶", command=lambda: self._step_preview(1),
            font=("Segoe UI", 8, "bold"), bg=BG_CARD, fg=TEXT_PRIMARY, relief=tk.FLAT, padx=10, cursor="hand2"
        ).pack(side=tk.RIGHT)

        action_box = tk.Frame(parent, bg=BG_PANEL, padx=16, pady=12)
        action_box.pack(fill=tk.X, side=tk.BOTTOM)

        self.run_btn = tk.Button(
            action_box,
            text="🚀 AKADEMİK ÇEVİRİYİ BAŞLAT",
            command=self._start_pipeline_thread,
            font=("Segoe UI Black", 11),
            bg=ACCENT_GREEN,
            fg="#052E16",
            activebackground="#34D399",
            relief=tk.FLAT,
            pady=10,
            cursor="hand2"
        )
        self.run_btn.pack(fill=tk.X)

    def _build_right_panel(self, parent: tk.Frame):
        prog_frame = tk.Frame(parent, bg=BG_PANEL, padx=18, pady=14)
        prog_frame.pack(fill=tk.X)

        top_p = tk.Frame(prog_frame, bg=BG_PANEL)
        top_p.pack(fill=tk.X, pady=(0, 6))

        tk.Label(top_p, text="AKTİF İŞ HATTI:", font=("Segoe UI", 9, "bold"), fg=TEXT_MUTED, bg=BG_PANEL).pack(side=tk.LEFT)
        tk.Label(top_p, textvariable=self.stage_text, font=("Segoe UI", 9, "bold"), fg=ACCENT_BLUE, bg=BG_PANEL, padx=8).pack(side=tk.LEFT)

        tk.Label(top_p, textvariable=self.timer_text, font=("Consolas", 10, "bold"), fg=ACCENT_GREEN, bg=BG_PANEL).pack(side=tk.RIGHT)
        tk.Label(top_p, text="SÜRE:", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=BG_PANEL, padx=6).pack(side=tk.RIGHT)

        self.pbar = ttk.Progressbar(
            prog_frame, variable=self.progress_val, maximum=100.0, style="Cyber.Horizontal.TProgressbar"
        )
        self.pbar.pack(fill=tk.X, pady=(2, 10))

        quick_bar = tk.Frame(prog_frame, bg=BG_PANEL)
        quick_bar.pack(fill=tk.X)

        self.btn_open_pdf = tk.Button(
            quick_bar, text="📄 Üretilen PDF'i Dışarıda Aç", command=self._open_external_pdf,
            font=("Segoe UI Semibold", 9), bg=BG_CARD, fg=TEXT_PRIMARY, relief=tk.FLAT, padx=12, pady=5, state=tk.DISABLED, cursor="hand2"
        )
        self.btn_open_pdf.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_copy_all = tk.Button(
            quick_bar, text="📋 Tüm Türkçe Metni Panoya Kopyala", command=self._copy_all_clean_txt,
            font=("Segoe UI Semibold", 9), bg=BG_CARD, fg=ACCENT_BLUE, relief=tk.FLAT, padx=12, pady=5, state=tk.DISABLED, cursor="hand2"
        )
        self.btn_copy_all.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_clear_cache = tk.Button(
            quick_bar, text="🧹 Önbelleği Yenile", command=self._clear_translation_cache,
            font=("Segoe UI", 8), bg=BG_CARD, fg=TEXT_MUTED, relief=tk.FLAT, padx=10, pady=5, cursor="hand2"
        )
        self.btn_clear_cache.pack(side=tk.RIGHT)

        self.notebook = ttk.Notebook(parent, style="Studio.TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 14))

        tab_console = tk.Frame(self.notebook, bg=BG_TERMINAL)
        self.notebook.add(tab_console, text="  💻 Canlı Sistem Telemetrisi  ")
        self.console_txt = self._create_studio_textbox(tab_console)

        tab_clean = tk.Frame(self.notebook, bg=BG_TERMINAL)
        self.notebook.add(tab_clean, text="  📝 Kopyalanabilir Türkçe Metin (.TXT)  ")
        self.clean_txt_view = self._create_studio_textbox(tab_clean)

        tab_review = tk.Frame(self.notebook, bg=BG_TERMINAL)
        self.notebook.add(tab_review, text="  🔍 EN ⇄ TR Akademik Karşılaştırma Stüdyosu  ")
        self.review_txt_view = self._create_studio_textbox(tab_review)

        tab_settings = tk.Frame(self.notebook, bg=BG_PANEL)
        self.notebook.add(tab_settings, text="  ⚙️ Çeviri Ayarları  ")
        self._build_settings_tab(tab_settings)

    def _build_settings_tab(self, parent: tk.Frame):
        pad = {"padx": 16, "pady": (10, 4)}
        tk.Label(parent, text="LM STUDIO (YEREL LLM)", font=("Segoe UI", 9, "bold"),
                 fg=ACCENT_BLUE, bg=BG_PANEL).pack(anchor="w", **pad)

        self.var_lm_url = tk.StringVar(value=str(self.settings.get("lmstudio_url", "")))
        self.var_lm_port = tk.StringVar(value=str(self.settings.get("lmstudio_port", "1234")))
        self.var_lm_model = tk.StringVar(value=str(self.settings.get("lmstudio_model", "")))

        for label, var in [
            ("Sunucu URL (boş = localhost:<port>/v1):", self.var_lm_url),
            ("Port:", self.var_lm_port),
            ("Model tercihi (boş = ilk yüklü model):", self.var_lm_model),
        ]:
            tk.Label(parent, text=label, font=("Segoe UI", 8), fg=TEXT_MUTED, bg=BG_PANEL).pack(anchor="w", padx=16)
            tk.Entry(parent, textvariable=var, font=("Consolas", 9), bg=BG_CARD, fg=TEXT_PRIMARY,
                     insertbackground="white", relief=tk.FLAT, width=44).pack(anchor="w", padx=16, pady=(2, 6))

        tk.Label(parent, text="BORU HATTI", font=("Segoe UI", 9, "bold"),
                 fg=ACCENT_BLUE, bg=BG_PANEL).pack(anchor="w", **pad)

        self.var_allow_ocr = tk.BooleanVar(value=bool(self.settings.get("allow_ocr", True)))
        tk.Checkbutton(parent, text="Taranmış sayfalarda Tesseract OCR (dijital PDF'lerde kapatabilirsiniz)",
                       variable=self.var_allow_ocr, bg=BG_PANEL, fg=TEXT_PRIMARY,
                       activebackground=BG_PANEL, selectcolor=BG_CARD,
                       font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=2)

        self.var_fresh = tk.BooleanVar(value=bool(self.settings.get("fresh", False)))
        tk.Checkbutton(parent, text="Checkpoint'i yok say (sıfırdan başla)",
                       variable=self.var_fresh, bg=BG_PANEL, fg=TEXT_PRIMARY,
                       activebackground=BG_PANEL, selectcolor=BG_CARD,
                       font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=2)

        self.var_pages = tk.StringVar(value=str(self.settings.get("pages", "")))
        tk.Label(parent, text="Sayfa aralığı (boş = tümü; örnek: 1-10 veya 1,2,5-8):",
                 font=("Segoe UI", 8), fg=TEXT_MUTED, bg=BG_PANEL).pack(anchor="w", padx=16, pady=(6, 0))
        tk.Entry(parent, textvariable=self.var_pages, font=("Consolas", 9), bg=BG_CARD, fg=TEXT_PRIMARY,
                 insertbackground="white", relief=tk.FLAT, width=44).pack(anchor="w", padx=16, pady=(2, 10))

        tk.Button(parent, text="💾 Ayarları Kaydet", command=self._save_settings_from_tab,
                  font=("Segoe UI Semibold", 9), bg=ACCENT_BLUE, fg="#070A12",
                  activebackground="#7DD3FC", relief=tk.FLAT, padx=14, pady=6, cursor="hand2"
                  ).pack(anchor="w", padx=16, pady=6)

        tk.Label(parent,
                 text="Not: Ayarlar 'ÇEVİRİYİ BAŞLAT' ile otomatik uygulanır ve kaydedilir.\n"
                      "Sayfa aralığı seçiminde seçilmeyen sayfalar çıktıda orijinal İngilizce kalır;\n"
                      "çıktı dosyası GUI'de <ad>_TR.pdf olarak adlandırılır — _p<aralik>_ULTIMATE.pdf\n"
                      "adlandırması yalnızca CLI (pdfai-translate) içindir.",
                 font=("Segoe UI", 8), fg=TEXT_MUTED, bg=BG_PANEL, justify=tk.LEFT
                 ).pack(anchor="w", padx=16, pady=(2, 10))

    def _collect_settings(self) -> dict:
        return {
            "lmstudio_url": self.var_lm_url.get().strip(),
            "lmstudio_port": self.var_lm_port.get().strip(),
            "lmstudio_model": self.var_lm_model.get().strip(),
            "allow_ocr": bool(self.var_allow_ocr.get()),
            "pages": self.var_pages.get().strip(),
            "fresh": bool(self.var_fresh.get()),
        }

    def _save_settings_from_tab(self):
        self.settings = self._collect_settings()
        if save_settings(self.settings):
            self.status_text.set("💾 Ayarlar kaydedildi (build/gui_settings.json).")
        else:
            self.status_text.set("⚠ Ayarlar kaydedilemedi (build/ klasörü yazılabilir mi?).")

    def _create_studio_textbox(self, parent: tk.Frame) -> tk.Text:
        scroll = tk.Scrollbar(parent, bg=BG_PANEL, troughcolor=BG_TERMINAL, relief=tk.FLAT)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        txt = tk.Text(
            parent,
            font=("Consolas", 10),
            bg=BG_TERMINAL,
            fg=TEXT_PRIMARY,
            insertbackground=ACCENT_BLUE,
            selectbackground=ACCENT_BLUE,
            selectforeground="#070A12",
            relief=tk.FLAT,
            padx=14,
            pady=12,
            wrap=tk.WORD,
            yscrollcommand=scroll.set,
            state=tk.DISABLED
        )
        txt.pack(fill=tk.BOTH, expand=True)
        scroll.config(command=txt.yview)

        txt.tag_config("info", foreground=ACCENT_BLUE, font=("Consolas", 10, "bold"))
        txt.tag_config("success", foreground=ACCENT_GREEN, font=("Consolas", 10, "bold"))
        txt.tag_config("warn", foreground=ACCENT_AMBER, font=("Consolas", 10, "bold"))
        txt.tag_config("en_line", foreground="#93C5FD")
        txt.tag_config("tr_line", foreground="#6EE7B7", font=("Consolas", 10, "bold"))
        txt.tag_config("muted", foreground=TEXT_MUTED)
        return txt

    def _refresh_telemetry_badges(self):
        # DONANIM OTOMATİK ALGILAMA VE CANLI GÜNCELLEME
        if torch.cuda.is_available():
            try:
                gname = torch.cuda.get_device_name(0).replace("NVIDIA GeForce ", "").replace("Laptop GPU", "").strip()
                self.badge_hw.config(text=f"⚡ GPU: {gname}", fg=ACCENT_GREEN)
            except Exception:
                self.badge_hw.config(text="⚡ GPU (CUDA Aktif)", fg=ACCENT_GREEN)
        else:
            threads = max(1, (os.cpu_count() or 4) - 1)
            self.badge_hw.config(text=f"⚡ CPU ({threads} Thread)", fg=ACCENT_AMBER)

        # C++ OpenMP Motoru rozeti (varsayılan olarak pasif: çıktısı henüz Python'a bağlı değil)
        from renderers.exporters import CPP_LAYOUT_ENGINE_ENABLED, find_cpp_engine_path
        if CPP_LAYOUT_ENGINE_ENABLED and find_cpp_engine_path():
            self.badge_cpp.config(text="⚙️ C++17 OpenMP: BAĞLI", fg=ACCENT_GREEN)
        else:
            self.badge_cpp.config(text="⚙️ Python Auto-Fit: AKTİF", fg=ACCENT_BLUE)

        # ÇEVİRİ ÖNBELLEĞİ (CACHE) SAYACI VE DOĞRULAMA
        cache_file = os.path.join("build", "translation_cache.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cnt = max(0, len(data) - 1)
                self.badge_cache.config(text=f"💾 {cnt} Cümle Önbellekte", fg=ACCENT_GREEN if cnt > 0 else TEXT_PRIMARY)
            except Exception:
                self.badge_cache.config(text="💾 Önbellek Hazır", fg=TEXT_PRIMARY)
        else:
            self.badge_cache.config(text="💾 Önbellek Boş", fg=TEXT_MUTED)

    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="Çevrilecek İngilizce PDF Belgesini Seçin",
            filetypes=[("PDF Belgeleri", "*.pdf"), ("Tüm Dosyalar", "*.*")]
        )
        if path:
            self._set_input_file(path)

    def _set_input_file(self, path: str):
        self.input_pdf.set(path)
        base, ext = os.path.splitext(path)
        if path.endswith("ornek_belge.pdf"):
            self.output_pdf.set(os.path.join(os.path.dirname(path), "cevirilmis_belge_ULTIMATE.pdf"))
        else:
            self.output_pdf.set(f"{base}_TR{ext}")

        self.showing_translated_preview = False
        self.toggle_preview_btn.config(state=tk.DISABLED, text="🔄 Türkçe Çıktıyı Göster")
        self._load_pdf_preview(path, is_translated=False)

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            title="Türkçe PDF Dosyasını Kaydet",
            defaultextension=".pdf",
            filetypes=[("PDF Belgeleri", "*.pdf")]
        )
        if path:
            self.output_pdf.set(path)

    def _load_pdf_preview(self, pdf_path: str, is_translated: bool = False):
        if not os.path.exists(pdf_path):
            return
        try:
            if self.preview_doc:
                self.preview_doc.close()
            self.preview_doc = fitz.open(pdf_path)
            if not is_translated:
                self.preview_page_idx = 0
            else:
                self.preview_page_idx = min(self.preview_page_idx, len(self.preview_doc) - 1)

            size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
            tag = "TÜRKÇE ÇIKTI" if is_translated else "KAYNAK PDF"
            self.doc_meta_lbl.config(
                text=f"[{tag}]  Sayfa: {len(self.preview_doc)}  |  Boyut: {size_mb:.2f} MB"
            )
            self.preview_title_lbl.config(
                text="CANLI ÖNİZLEME (TÜRKÇE PDF)" if is_translated else "CANLI ÖNİZLEME (ORİJİNAL PDF)",
                fg=ACCENT_GREEN if is_translated else ACCENT_BLUE
            )
            self.root.after(80, self._render_current_preview_page)
        except Exception as e:
            self.doc_meta_lbl.config(text=f"Önizleme hatası: {e}")

    def _render_current_preview_page(self):
        if not self.preview_doc or len(self.preview_doc) == 0:
            return
        try:
            page = self.preview_doc[self.preview_page_idx]
            cw = max(240, self.canvas_preview.winfo_width() - 16)
            ch = max(260, self.canvas_preview.winfo_height() - 16)

            scale = min(cw / max(1.0, page.rect.width), ch / max(1.0, page.rect.height))
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
            mode = "RGBA" if pix.alpha else "RGB"
            img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)

            self.tk_preview_img = ImageTk.PhotoImage(img)
            self.canvas_preview.delete("all")
            self.canvas_preview.create_image(cw // 2 + 8, ch // 2 + 8, image=self.tk_preview_img, anchor=tk.CENTER)
            self.page_counter_lbl.config(text=f"Sayfa: {self.preview_page_idx + 1} / {len(self.preview_doc)}")
        except Exception:
            pass

    def _step_preview(self, delta: int):
        if not self.preview_doc:
            return
        new_idx = self.preview_page_idx + delta
        if 0 <= new_idx < len(self.preview_doc):
            self.preview_page_idx = new_idx
            self._render_current_preview_page()

    def _toggle_preview_source(self):
        in_p = self.input_pdf.get().strip()
        out_p = self.output_pdf.get().strip()
        if not os.path.exists(out_p):
            return
        self.showing_translated_preview = not self.showing_translated_preview
        if self.showing_translated_preview:
            self.toggle_preview_btn.config(text="🔄 Orijinal PDF'i Göster", fg=ACCENT_BLUE)
            self._load_pdf_preview(out_p, is_translated=True)
        else:
            self.toggle_preview_btn.config(text="🔄 Türkçe Çıktıyı Göster", fg=ACCENT_GREEN)
            self._load_pdf_preview(in_p, is_translated=False)

    def _on_progress_event(self, event: str, detail: dict):
        """Motor iş parçacığından gelir; Tk erişimi ana iş parçacığına aktarılır."""
        self._progress_source = "callback"
        self.root.after(0, self._apply_progress_event, event, detail)

    def _apply_progress_event(self, event: str, detail: dict):
        if event == "stage":
            self.stage_text.set(detail.get("label", ""))
            self.progress_val.set(float(detail.get("percent", self.progress_val.get())))
        elif event == "progress":
            done = int(detail.get("done", 0))
            total = max(1, int(detail.get("total", 1)))
            pct = 18.0 + (done / total) * 62.0
            self.progress_val.set(min(80.0, pct))
            self.stage_text.set(f"2/4 • Nöral Çeviri: {done} / {total} Blok (%{int((done / total) * 100)})")
        elif event == "done":
            self.stage_text.set("TAMAMLANDI • Tüm Çıktılar Hazır")
            self.progress_val.set(100.0)

    def process_console_output(self, text: str):
        self.console_txt.config(state=tk.NORMAL)
        tag = None
        if any(k in text for k in ("[DONANIM]", "[ÖNBELLEK]", "[İŞLEM BAŞLADI]", "1. [YEREL")):
            tag = "info"
        elif any(k in text for k in ("[BAŞARILI]", "Kusursuz PDF", "-> Çeviri Modeli")):
            tag = "success"
        elif any(k in text for k in ("[HİBRİT OCR]", "[UYARI]", "[DONANIM UYARISI]")):
            tag = "warn"

        if tag:
            self.console_txt.insert(tk.END, text, tag)
        else:
            self.console_txt.insert(tk.END, text)
        self.console_txt.see(tk.END)
        self.console_txt.config(state=tk.DISABLED)

        # Yüzde/aşama eşlemesi: callback kanalı devredeyse kazıma yalnızca yedek.
        if self._progress_source == "console":
            clean = text.strip()
            if "yerel diskten" in clean:
                self.stage_text.set("1/4 • Nöral Model Yükleniyor...")
                self.progress_val.set(8.0)
            elif "Tespit Edilen Toplam" in clean:
                m = re.search(r':\s*(\d+)', clean)
                if m:
                    self.total_blocks = max(1, int(m.group(1)))
                self.stage_text.set(f"2/4 • Akademik Çeviri ({self.total_blocks} Blok)...")
                self.progress_val.set(18.0)
            elif "Çeviri İlerlemesi:" in clean:
                m = re.search(r'(\d+)/(\d+)', clean)
                if m:
                    done, tot = int(m.group(1)), max(1, int(m.group(2)))
                    pct = 18.0 + (done / tot) * 62.0
                    self.progress_val.set(min(80.0, pct))
                    self.stage_text.set(f"2/4 • Nöral Çeviri: {done} / {tot} Blok (%{int((done/tot)*100)})")
            elif "[C++ AiEngine]" in clean:
                self.stage_text.set("3/4 • C++17 OpenMP Mizanpaj Hesaplaması...")
                self.progress_val.set(85.0)
            elif "[CERRAHİ RENDER]" in clean:
                self.stage_text.set("4/4 • Cerrahi PDF Render & TXT Üretimi...")
                self.progress_val.set(92.0)
            elif "[BAŞARILI]" in clean:
                self.stage_text.set("TAMAMLANDI • Tüm Çıktılar Hazır")
                self.progress_val.set(100.0)

    def _update_clock(self):
        if not self.is_running:
            return
        elapsed = int(time.time() - self.start_time)
        mins, secs = divmod(elapsed, 60)
        self.timer_text.set(f"{mins:02d}:{secs:02d}")
        self.root.after(500, self._update_clock)

    def _start_pipeline_thread(self):
        if self.is_running:
            return
        in_p = self.input_pdf.get().strip()
        out_p = self.output_pdf.get().strip()

        if not in_p or not os.path.exists(in_p):
            messagebox.showerror("Eksik Dosya", "Lütfen geçerli bir İngilizce PDF belgesi seçin!")
            return

        # Ayarları topla, doğrula ve kalıcı hale getir
        self.settings = self._collect_settings()
        pages = None
        if self.settings["pages"]:
            try:
                with fitz.open(in_p) as probe:
                    total_pages = len(probe)
                pages = pdf_bridge.parse_page_selection(self.settings["pages"], total_pages)
            except ValueError as exc:
                messagebox.showerror("Geçersiz Sayfa Aralığı", str(exc))
                return
        save_settings(self.settings)
        apply_lmstudio_env(self.settings)

        self.is_running = True
        self.start_time = time.time()
        self.progress_val.set(2.0)
        self.stage_text.set("Başlatılıyor • Belge Düzeni Analizi (DLA)...")
        self.status_text.set(f"İŞLENİYOR: {os.path.basename(in_p)}  •  Lütfen bekleyin...")

        self.run_btn.config(state=tk.DISABLED, text="⏳ NÖRAL MOTOR ÇALIŞIYOR...", bg=BG_CARD, fg=ACCENT_BLUE)
        self.btn_open_pdf.config(state=tk.DISABLED)
        self.btn_copy_all.config(state=tk.DISABLED)
        self.notebook.select(0)

        for widget in (self.console_txt, self.clean_txt_view, self.review_txt_view):
            widget.config(state=tk.NORMAL)
            widget.delete("1.0", tk.END)
            widget.config(state=tk.DISABLED)

        self._update_clock()
        threading.Thread(
            target=self._worker_task,
            args=(in_p, out_p, self.settings["allow_ocr"], not self.settings["fresh"], pages),
            daemon=True
        ).start()

    def _worker_task(self, in_p: str, out_p: str, allow_ocr: bool, resume: bool, pages):
        try:
            pdf_bridge.run_pipeline(
                in_p, out_p,
                progress_cb=self._on_progress_event,
                allow_ocr=allow_ocr,
                resume=resume,
                pages=pages,
            )
            self.root.after(0, self._on_pipeline_complete, out_p)
        except Exception as e:
            print(f"\n[KRİTİK HATA] {e}\n")
            self.root.after(0, lambda err_msg=str(e): messagebox.showerror("İşlem Hatası", err_msg))
        finally:
            self.root.after(0, self._unlock_ui)

    def _on_pipeline_complete(self, out_p: str):
        actual_pdf = out_p
        alt_pdf = os.path.splitext(out_p)[0] + "_YENI.pdf"
        if os.path.exists(alt_pdf) and (not os.path.exists(out_p) or os.path.getmtime(alt_pdf) > os.path.getmtime(out_p)):
            actual_pdf = alt_pdf
            self.output_pdf.set(actual_pdf)

        base = os.path.splitext(actual_pdf)[0]
        clean_txt = f"{base}.txt"
        review_txt = f"{base}_INCELEME.txt"

        if os.path.exists(clean_txt):
            with open(clean_txt, "r", encoding="utf-8") as f:
                content = f.read()
            self.clean_txt_view.config(state=tk.NORMAL)
            self.clean_txt_view.insert(tk.END, content)
            self.clean_txt_view.config(state=tk.DISABLED)

        if os.path.exists(review_txt):
            with open(review_txt, "r", encoding="utf-8") as f:
                lines = f.readlines()
            self.review_txt_view.config(state=tk.NORMAL)
            for ln in lines:
                if ln.startswith("EN (Orijinal)"):
                    self.review_txt_view.insert(tk.END, ln, "en_line")
                elif ln.startswith("TR (Çeviri)"):
                    self.review_txt_view.insert(tk.END, ln, "tr_line")
                elif ln.startswith("["):
                    self.review_txt_view.insert(tk.END, ln, "info")
                else:
                    self.review_txt_view.insert(tk.END, ln, "muted")
            self.review_txt_view.config(state=tk.DISABLED)

        self.showing_translated_preview = True
        self.toggle_preview_btn.config(state=tk.NORMAL, text="🔄 Orijinal PDF'i Göster", fg=ACCENT_BLUE)
        self._load_pdf_preview(actual_pdf, is_translated=True)

        self.btn_open_pdf.config(state=tk.NORMAL)
        self.btn_copy_all.config(state=tk.NORMAL)
        self._refresh_telemetry_badges()
        self.status_text.set(f"BAŞARIYLA TAMAMLANDI  •  Çıktı: {os.path.basename(actual_pdf)}")

    def _unlock_ui(self):
        self.is_running = False
        self.run_btn.config(
            state=tk.NORMAL,
            text="🚀 AKADEMİK ÇEVİRİYİ BAŞLAT",
            bg=ACCENT_GREEN,
            fg="#052E16"
        )

    def _open_external_pdf(self):
        out_p = self.output_pdf.get().strip()
        if not os.path.exists(out_p):
            return
        if os.name == "nt":
            os.startfile(out_p)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", out_p])
        else:
            subprocess.Popen(["xdg-open", out_p])

    def _copy_all_clean_txt(self):
        content = self.clean_txt_view.get("1.0", tk.END).strip()
        if content:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.status_text.set("📋 Tüm Türkçe metin ve formüller panoya kopyalandı!")
            messagebox.showinfo("Kopyalandı", "Tüm Türkçe metin ve formüller panoya kopyalandı (Ctrl+V ile yapıştırabilirsiniz).")

    def _clear_translation_cache(self):
        cache_file = os.path.join("build", "translation_cache.json")
        if os.path.exists(cache_file):
            try:
                os.remove(cache_file)
                self._refresh_telemetry_badges()
                self.status_text.set("🧹 Çeviri önbelleği temizlendi.")
                messagebox.showinfo("Önbellek Temizlendi", "Çeviri önbelleği sıfırlandı.")
            except Exception:
                pass
        else:
            messagebox.showinfo("Bilgi", "Temizlenecek aktif önbellek dosyası bulunamadı.")


if __name__ == "__main__":
    root = tk.Tk()
    studio = EnterpriseTranslatorStudio(root)
    root.mainloop()