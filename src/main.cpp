#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <sstream>
#include <omp.h>
#include <iomanip>

using namespace std;

struct TextBlock {
    int id;
    int page;
    float x;
    float y;
    float w;
    float h;
    float fontsize;
    string original_text;
    string translated_text;
};

vector<string> split(const string& s, char delimiter) {
    vector<string> tokens;
    string token;
    istringstream tokenStream(s);
    while (getline(tokenStream, token, delimiter)) {
        tokens.push_back(token);
    }
    return tokens;
}

int main(int argc, char* argv[]) {
    if (argc < 3) return 1;

    string inputFile = argv[1];
    string outputFile = argv[2];

    vector<TextBlock> blocks;
    ifstream infile(inputFile);

    if (!infile.is_open()) return 1;

    string line;
    while (getline(infile, line)) {
        vector<string> parts = split(line, '|');
        if (parts.size() >= 9) {
            TextBlock block;
            block.id = stoi(parts[0]);
            block.page = stoi(parts[1]);
            block.x = stof(parts[2]);
            block.y = stof(parts[3]);
            block.w = stof(parts[4]);
            block.h = stof(parts[5]);
            block.fontsize = stof(parts[6]);

            block.original_text = parts[7];
            block.translated_text = parts[8];
            for (size_t i = 9; i < parts.size(); ++i) {
                block.translated_text += " " + parts[i];
            }
            blocks.push_back(block);
        }
    }
    infile.close();

    int num_blocks = blocks.size();

#pragma omp parallel for
    for (int i = 0; i < num_blocks; ++i) {
        if (blocks[i].original_text.length() > 0 && blocks[i].translated_text.length() > 0) {
            float length_ratio = (float)blocks[i].original_text.length() / (float)blocks[i].translated_text.length();
            if (length_ratio < 1.0f) {
                // Türkçe uzadıysa fontu orantılı küçült ama 6.5'in altına düşürüp okunmaz hale getirme
                blocks[i].fontsize = max(blocks[i].fontsize * length_ratio, 6.5f);
            }
        }
    }

    ofstream outfile(outputFile);
    if (!outfile.is_open()) return 1;

    outfile << fixed << setprecision(2);
    for (const auto& block : blocks) {
        outfile << block.id << "|" << block.page << "|" << block.x << "|"
            << block.y << "|" << block.w << "|" << block.h << "|"
            << block.fontsize << "|" << block.translated_text << "\n";
    }
    outfile.close();

    return 0;
}