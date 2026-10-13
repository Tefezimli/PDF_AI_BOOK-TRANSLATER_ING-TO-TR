#include "pdf_layout.h"
#include <iomanip>

void PDFLayoutManager::add_block(int id, const std::string& text, float x, float y, float w, float h, float font_size) {
    TextBlock block;
    block.id = id;
    block.original_text = text;
    block.translated_text = "";
    block.box = { x, y, w, h };
    block.font_size = font_size;
    block.adapted_font_size = font_size;
    blocks.push_back(block);
}

void PDFLayoutManager::adapt_layout() {
    for (auto& block : blocks) {
        if (block.translated_text.empty()) continue;

        // Yaklaşık karakter genişliği hesabı (Monospace/Ortalama font faktörü: font_size * 0.55f)
        float char_width_factor = 0.55f;
        float original_estimated_len = block.original_text.length() * block.font_size * char_width_factor;
        float translated_estimated_len = block.translated_text.length() * block.font_size * char_width_factor;

        // Eğer yeni metin kutunun genişliğini aşıyorsa font boyutunu küçült
        if (translated_estimated_len > block.box.width) {
            float scale_factor = block.box.width / translated_estimated_len;
            block.adapted_font_size = block.font_size * scale_factor;
        }
        else {
            block.adapted_font_size = block.font_size;
        }
    }
}

void PDFLayoutManager::print_layout_report() const {
    std::cout << "\n=================== PDF SEMATIK KOORDINAT RAPORU ===================\n";
    for (const auto& b : blocks) {
        std::cout << "[Blok ID: " << b.id << "]\n";
        std::cout << "  Konum (X, Y)       : (" << b.box.x << ", " << b.box.y << ")\n";
        std::cout << "  Kutu (En x Boy)    : " << b.box.width << " x " << b.box.height << " pt\n";
        std::cout << "  Orijinal Metin     : \"" << b.original_text << "\"\n";
        std::cout << "  Cevrilen/Duzenlenen: \"" << b.translated_text << "\"\n";
        std::cout << "  Orijinal Punto     : " << b.font_size << " pt\n";
        std::cout << "  Uyarli Yeni Punto  : " << std::fixed << std::setprecision(2) << b.adapted_font_size << " pt\n";
        if (b.adapted_font_size < b.font_size) {
            std::cout << "  -> DURUM: Metin uzadigi icin sema bozulmadi, punto dinamik kucultuldu.\n";
        }
        else {
            std::cout << "  -> DURUM: Sema korundu, standart punto kullanildi.\n";
        }
        std::cout << "--------------------------------------------------------------------\n";
    }
}