import torch
from transformers import MarianMTModel, MarianTokenizer
import numpy as np
import os

model_name = "Helsinki-NLP/opus-mt-en-de"
print(f"=== {model_name} Modeli Indiriliyor ===")

# 1. Tokenizer ve Modeli HuggingFace'den çek
tokenizer = MarianTokenizer.from_pretrained(model_name)
model = MarianMTModel.from_pretrained(model_name)

# 2. Embedding (Kelime Gömme) matrisini al
# Bu matris, on binlerce kelimenin 512 boyutlu uzaydaki sayısal karşılıklarını tutar.
embeddings = model.get_input_embeddings().weight.data.numpy()

vocab_size, hidden_dim = embeddings.shape
print(f"Kelime Dagarcigi (Vocab Size): {vocab_size}")
print(f"Vektor Boyutu (Hidden Dim): {hidden_dim}")
print(f"Toplam Parametre Sayisi: {vocab_size * hidden_dim}")

# 3. C++ Motorumuzun okuyabilmesi için saf Float32 Binary (.bin) olarak kaydet
output_dir = "build"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

bin_filename = os.path.join(output_dir, "marian_embeddings.bin")

# Numpy dizisini doğrudan bayt olarak diske yazıyoruz
embeddings.astype(np.float32).tofile(bin_filename)

print(f"\nBasarili! Agirliklar C++ motoru icin '{bin_filename}' dosyasina kaydedildi.")