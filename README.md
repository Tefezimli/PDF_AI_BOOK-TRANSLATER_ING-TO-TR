# PDF AI Book Translator (EN -> TR) 🚀

> **Açık kaynaklı, tamamen yerel ve internetsiz akademik PDF çeviri motoru.**  
> Python ve C++ mimarisiyle çalışan bu araç, Belge Düzeni Analizi (DLA) kullanarak ders kitaplarındaki matematik formüllerini, grafikleri ve mizanpajı bozmadan İngilizceden Türkçeye çevirir. Yüksek gizlilik odaklı, güvenli ve donanım dostudur.

A high-performance hybrid PDF processing and translation engine combining **C++17 (OpenMP)** for parallel text layout computing with **Python** for neural translation and OCR layout analysis.

---

## 📌 Features

- **Hybrid Architecture**:
  - **C++17 Engine**: High-throughput parallel layout parsing, text-box scaling, and dynamic font adjustment powered by OpenMP.
  - **Python Bridge**: PyMuPDF-based PDF extraction, Tesseract / Surya OCR, MarianMT translation (`Helsinki-NLP`), and layout preservation.
- **Dynamic Typography Scaling**: Automatically recalculates translated text bounding boxes and dynamically adjusts font sizing to fit document layout without clipping.
- **Hardware Fallback**: Resilient device selection (CUDA GPU support with automatic CPU fallback).
- **Custom Tensor & Tokenizer Core**: Native C++ tensor operations and tokenizer abstractions designed for reading binary model weights.

---

## 📁 Project Structure

```
pdf_ai_engine/
├── include/                 # C++ Header files
│   ├── pdf_layout.h         # Layout data structures & bounding boxes
│   ├── tensor.h             # Native tensor operations
│   └── tokenizer.h          # Fast tokenization interface
├── src/                     # C++ Source implementations
│   ├── main.cpp             # Layout text-fitting CLI engine (OpenMP)
│   ├── pdf_layout.cpp       # Layout logic
│   ├── tensor.cpp           # Tensor matrix operations
│   └── tokenizer.cpp        # Tokenizer implementation
├── CMakeLists.txt           # CMake build configuration
├── requirements.txt         # Python dependencies
├── pdf_bridge.py            # Main PDF translation & OCR orchestration script
└── export_model.py          # Weight exporter (HuggingFace -> Binary)
```

---

## 🛠️ Installation & Setup

### 1. Prerequisites
- **C++ Compiler** with C++17 and OpenMP support (MSVC, GCC, or Clang)
- **CMake** (>= 3.10)
- **Python** (>= 3.10)
- **Tesseract OCR** (installed at standard path or configured in `pdf_bridge.py`)

### 2. Python Environment Setup
```bash
# Create and activate virtual environment
python -m venv ai_env
ai_env\Scripts\activate       # On Windows
# source ai_env/bin/activate  # On Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### 3. Build C++ Engine
```bash
mkdir build
cd build
cmake ..
cmake --build . --config Release
cd ..
```

---

## 🚀 Usage

### 1. Export Model Weights (Optional)
Export HuggingFace MarianMT embeddings to binary format for the C++ engine:
```bash
python export_model.py
```

### 2. Run the PDF Processing Pipeline
Process and translate PDF documents while preserving layout:
```bash
python pdf_bridge.py
```

---

## 📄 License
MIT License.
