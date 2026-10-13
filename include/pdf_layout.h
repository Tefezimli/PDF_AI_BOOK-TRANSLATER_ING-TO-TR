#pragma once
#include <string>
#include <vector>
#include <iostream>

struct BoundingBox {
    float x;
    float y;
    float width;
    float height;
};

struct TextBlock {
    int id;
    std::string original_text;
    std::string translated_text;
    BoundingBox box;
    float font_size;
    float adapted_font_size;
};

class PDFLayoutManager {
public:
    std::vector<TextBlock> blocks;

    void add_block(int id, const std::string& text, float x, float y, float w, float h, float font_size);

    // Çeviri sonrası metnin kutuya sığıp sığmadığını denetleyip fontu yeniden hesaplama
    void adapt_layout();

    void print_layout_report() const;
};