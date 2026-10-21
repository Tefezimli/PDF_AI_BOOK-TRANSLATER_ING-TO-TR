# PDF AI Book & Slide Translator (EN ➔ TR) 🚀

<p align="center">
  <a href="README.md"><b>🇬🇧 English Documentation</b></a> •
  <a href="README_TR.md">🇹🇷 Türkçe Dokümantasyon</a>
</p>

[![Language: C++17](https://img.shields.io/badge/Language-C%2B%2B17-00599C.svg?style=flat&logo=c%2B%2B)](https://isocpp.org/)
[![Language: Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=flat&logo=python)](https://www.python.org/)
[![UI: Obsidian Cyber-GUI](https://img.shields.io/badge/GUI-Obsidian%20Workstation-38BDF8.svg?style=flat)](#-obsidian-cyber-workstation-gui)
[![Framework: PyTorch](https://img.shields.io/badge/PyTorch-CUDA%20%2F%20RTX%205080%20Ready-EE4C2C.svg?style=flat&logo=pytorch)](https://pytorch.org/)
[![Acceleration: OpenMP](https://img.shields.io/badge/Acceleration-OpenMP%20Multi--threading-green.svg)](https://www.openmp.org/)
[![Privacy: 100% Offline](https://img.shields.io/badge/Privacy-100%25%20Offline%20%26%20Air--Gapped-success.svg)](#-privacy--security)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **A high-performance, 100% offline and air-gapped hybrid (C++17 + Python) neural translation workstation engineered for academic textbooks, lecture slides, and technical research papers—preserving mathematical formulas, typography, and complex document layouts with millimeter precision.**

---

<p align="center">
  <img src="assets/app_preview.png" alt="PDF AI Engine Pro Workstation Preview" width="100%" />
</p>

---

## ⚡ Quick Start (Zero Configuration & One-Click Setup)

Designed for seamless out-of-the-box operation on Windows without complex manual setup:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STEP 0:  Download the Project:                                                 │
│           Click the green `<> Code` button on GitHub, select `Download ZIP`,    │
│           and extract the archive (or run `git clone <repo-url>`).              │
├─────────────────────────────────────────────────────────────────────────────────┤
│  STEP 1:  Double-click `Kurulum_Yap.bat`.                                      │
│           (Automatically sets up Python virtual environment, installs PyTorch   │
│           with RTX 5080 / CUDA 12.8 support, and downloads the offline model.)  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  STEP 2:  Double-click `Baslat.bat`.                                           │
│           (Launches the modern Obsidian Cyber-Workstation desktop GUI.)        │
├─────────────────────────────────────────────────────────────────────────────────┤
│  STEP 3:  Select your English PDF and click "🚀 ÇEVİRİYİ BAŞLAT"!              │
└─────────────────────────────────────────────────────────────────────────────────┘
```

> 💡 **Note:** Once the initial setup is complete, the entire application operates **100% offline without requiring internet access**.

---

## 💻 Developer & Command Line Usage

For developers who prefer command-line execution:

### Windows (PowerShell / CMD)
```powershell
# 1. Activate virtual environment
.\ai_env\Scripts\activate

# 2. Launch Desktop GUI:
python app_gui.py

# OR run translation pipeline directly via CLI:
python pdf_bridge.py
```

### Linux / macOS
```bash
# 1. Create and activate virtual environment
python3 -m venv ai_env
source ai_env/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch GUI
python3 app_gui.py
```

---

## 🖥️ Obsidian Cyber-Workstation GUI

The native desktop workstation in [`app_gui.py`](app_gui.py) provides a comprehensive suite of visual tools:

* 📁 **Smart Document Picker:** Browse and inspect input PDF documents; automatically displays page count and metadata.
* 👁️ **Dual-Mode Live Page Preview:** Instantly toggle and inspect original English pages against translated Turkish vector pages in real-time.
* 📊 **Live Hardware Telemetry:** Automatically discovers and displays active hardware acceleration (NVIDIA RTX 5080 sm_120 Blackwell, CUDA cores, or multi-threaded CPU fallback).
* 🛡️ **Air-Gapped Protocol Monitor:** Verifies 100% offline isolation and ensures zero data leakage.
* 📝 **Bilingual Review Inspector:** Side-by-side inspection table presenting original English sentences alongside translated Turkish paragraphs with one-click copying.
* ⚡ **Live Progress & Console Logs:** Real-time percentage progress bar and terminal logs detailing OCR, mathematical masking, and C++ layout fitting.

---

## 🛡️ Why PDF AI Engine? (Traditional Translators vs. PDF AI Engine)

<p align="center">
  <img src="assets/comparison_demo.png" alt="PDF AI Engine Before and After Comparison" width="100%" />
</p>

Standard translation tools inevitably break formulas and corrupt document geometry in academic contexts:

| Comparison Criteria | Standard Translators (Google / DeepL) | 🚀 PDF AI Engine Pro (v14.0) |
| :--- | :--- | :--- |
| **Mathematics & Formulas** | Corrupts equations into plain text ($x^2 \to x2$, $r^{n-1} \to rn-1$) | 🛡️ **Unicode Super/Subscripts & MTH-Token Shield** preserve formulas 100% |
| **Document Layout & Typography** | Drifts text boxes, misaligns tables and diagram callouts | ⚡ **C++17 OpenMP & Dynamic Font Auto-Fit** ensure millimeter-precise alignment |
| **Background Color & Contrast** | Pastes white text boxes over dark slides, ruining aesthetics | 🎨 **Outer-Ring Color Sampling:** White text on dark themes, dark text on light themes |
| **Academic Terminology** | Literal/generic translations (*Radix* $\to$ *Root*) | 📚 **Domain Glossary:** *Radix Complement* $\to$ *Taban Tümleyeni* |
| **Privacy & Security** | Uploads documents to third-party cloud servers | 🔒 **100% Offline (Air-Gapped):** No data ever leaves your local machine |
| **Hardware Optimization** | Limited hardware acceleration | 🚀 **RTX 5080 (CUDA 12.8 / sm_120) Tensor Cores** + Multi-threaded CPU Fallback |
| **Output Flexibility** | Produces only a single PDF output | 📑 **Tri-Output System:** Selectable PDF + Clean TXT + Bilingual Review TXT |

---

## 🏛️ System Architecture & Workflow

```mermaid
flowchart TD
    A[Input Document: PDF] --> B{Document Layout Analysis}
    
    B -->|Digital Vector Text| C[1. Typography & Text Extraction<br/>PyMuPDF: Font, Size, Bounding Box]
    B -->|Scanned / Raster Image| D[1. Adaptive OCR Layer<br/>OpenCV & Dual-Pass Tesseract]
    
    C --> E[2. Math & Sub/Superscript Reconstruction<br/>Unicode Mapping & Baseline Detection]
    D --> E
    
    E --> F[3. Formula & Equation Shielding<br/>MTH Security Token Shield]
    F --> G[4. Engineering Terminology Dictionary<br/>Digital Logic & Computer Architecture]
    G --> H[5. Neural Machine Translation<br/>Helsinki-NLP MarianMT Offline]
    H --> I[6. Formula Restoration & Post-Editing<br/>Exact Equation Re-injection]
    
    I --> J[7. C++17 AiEngine & Python Auto-Fit<br/>OpenMP Parallel Bbox & Font Scaling]
    J --> K[8. Surgical Vector Rendering<br/>Background Matching & Contrast Guarantee]
    
    K --> L[Output 1: Selectable Turkish PDF]
    K --> M[Output 2: Clean Turkish TXT Transcript]
    K --> N[Output 3: Bilingual Comparison TXT]
```

### 🔄 8-Stage End-to-End Processing Pipeline:

1. **📄 Document Layout Analysis (DLA):** Classifies pages as digital vector text or raster scanned slides. Digital text is extracted directly via PyMuPDF; scanned slides are processed through OpenCV adaptive thresholding and dual-pass Tesseract OCR.
2. **📐 Math & Index Reconstruction:** Preserves superscripts ($x^2, r^{n-1}$) and subscripts ($a_0, N_1$) at the Unicode character level.
3. **🛡️ Formula Shielding (MTH Shield):** Encapsulates standalone and inline formulas using unique `MTH0X`, `MTH1X` tokens to prevent neural model corruption.
4. **📚 Academic & Engineering Glossary:** Applies deterministic rule-based corrections for computer architecture and digital logic terms (*Radix Complement* $\to$ *Taban Tümleyeni*, *Discard end carry* $\to$ *Son eldeyi atın*).
5. **🧠 Neural Machine Translation:** Runs local MarianMT inference on GPU/CPU with mini-batching and repeat penalty optimizations.
6. **🔓 Formula Restoration:** Restores shielded tokens back into translated Turkish sentences with zero mathematical loss.
7. **⚡ C++17 AiEngine & Dynamic Font Auto-Fit:** Calculates language expansion ratios and iteratively optimizes font size to fit bounding boxes using OpenMP parallel threads.
8. **🎨 Surgical Vector Rendering:** Samples outer-ring background colors and renders sharp vector glyphs with strict contrast guarantees (white on dark backgrounds, dark on light backgrounds).

---

## 📑 Tri-Output Production System

Every processed document concurrently produces three complementary formats:

1. **Searchable & Selectable Turkish PDF (`*_ULTIMATE.pdf`):** A visual twin of the original document with surgical in-place replacement and selectable vector text.
2. **Clean Turkish Transcript (`*_ULTIMATE.txt`):** A clean page-by-page transcript containing pure Turkish text and reconstructed mathematical formulas.
3. **Bilingual Review File (`*_INCELEME.txt`):** A side-by-side comparative inspection document displaying original English blocks against Turkish translations.

---

## 📁 Repository Directory Structure

```
pdf_ai_engine/
├── assets/                  # Showcase and comparison visual assets
│   ├── app_preview.png      # Obsidian Cyber Workstation GUI preview
│   └── comparison_demo.png  # Before / After academic translation comparison
├── include/                 # C++ Header Files
│   ├── pdf_layout.h         # Document layout and BoundingBox structures
│   ├── tensor.h             # Custom C++ tensor and matrix optimizations
│   └── tokenizer.h          # High-speed word tokenization interface
├── src/                     # C++ Source Files
│   ├── main.cpp             # OpenMP multi-threaded font adaptation engine
│   ├── pdf_layout.cpp       # Layout calculation routines
│   ├── tensor.cpp           # Tensor multiplication logic
│   └── tokenizer.cpp        # C++ tokenizer implementation
├── app_gui.py               # Obsidian Cyber-Workstation desktop GUI
├── pdf_bridge.py            # Core AI, OCR, layout, and rendering engine
├── export_model.py          # MarianMT model exporter to Float32 binary (.bin)
├── Kurulum_Yap.bat          # 1-Click Windows automated setup wizard
├── Baslat.bat               # 1-Click Windows GUI launcher
├── CMakeLists.txt           # C++ CMake build configuration
├── requirements.txt         # Python package dependencies
├── Giris.txt                # Quick reference cheat-sheet
├── LICENSE                  # MIT License
├── README.md                # Primary English documentation
└── README_TR.md             # Turkish documentation
```

---

## ⚙️ Building C++ AiEngine (Optional / Performance Boost)

```bash
mkdir build
cd build
cmake ..
cmake --build . --config Release
cd ..
```

> ℹ️ **Note:** CMake and C++ compiler are optional. If not installed, `pdf_bridge.py` seamlessly falls back to its built-in Python dynamic font auto-fit algorithm.

---

## ❓ Frequently Asked Questions (FAQ)

<details>
<summary><b>1. Does this work completely offline without internet?</b></summary>
Yes! Once <code>Kurulum_Yap.bat</code> downloads the translation model during initial setup, the application operates 100% offline with zero external network dependencies.
</details>

<details>
<summary><b>2. Can I run this without an NVIDIA graphics card?</b></summary>
Yes. The engine automatically detects available hardware. If no CUDA GPU is detected, it smoothly transitions to multi-threaded CPU processing.
</details>

<details>
<summary><b>3. Does it handle scanned slides and dark-themed presentations?</b></summary>
Yes. Dual-pass adaptive OCR with outer-ring color sampling reliably extracts and renders text across both bright white slides and inverted dark themes.
</details>

<details>
<summary><b>4. Will mathematical formulas and superscripts be corrupted?</b></summary>
No. The MTH Token Shield locks all equations prior to translation and restores them in their original mathematical structure afterward.
</details>

---

## 🔒 Privacy & Security

* **100% Air-Gapped & Local:** No documents, text, or telemetry are ever transmitted to external cloud servers.
* **Hugging Face Telemetry Disabled:** Explicitly disabled in code (`HF_HUB_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`).

---

## 📄 License

This project is open-source under the [MIT License](LICENSE). You are free to use, modify, and distribute it.
