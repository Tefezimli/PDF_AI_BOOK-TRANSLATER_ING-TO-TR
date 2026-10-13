#include "tokenizer.h"
#include <sstream>
#include <cassert>

Tokenizer::Tokenizer() : vocab_size(0) {
    // Özel belirteçler
    add_word("<pad>"); // ID 0
    add_word("<unk>"); // ID 1 (Bilinmeyen kelimeler için)
}

void Tokenizer::add_word(const std::string& word) {
    if (vocab_to_id.find(word) == vocab_to_id.end()) {
        vocab_to_id[word] = vocab_size;
        id_to_vocab[vocab_size] = word;
        vocab_size++;
    }
}

std::vector<int> Tokenizer::encode(const std::string& text) const {
    std::vector<int> tokens;
    std::stringstream ss(text);
    std::string word;

    while (ss >> word) {
        auto it = vocab_to_id.find(word);
        if (it != vocab_to_id.end()) {
            tokens.push_back(it->second);
        }
        else {
            tokens.push_back(1); // <unk>
        }
    }
    return tokens;
}

std::string Tokenizer::decode(const std::vector<int>& tokens) const {
    std::string text = "";
    for (size_t i = 0; i < tokens.size(); ++i) {
        auto it = id_to_vocab.find(tokens[i]);
        if (it != id_to_vocab.end()) {
            text += it->second;
        }
        else {
            text += "<unk>";
        }
        if (i + 1 < tokens.size()) text += " ";
    }
    return text;
}

Tensor Tokenizer::get_embeddings(const std::vector<int>& tokens, const Tensor& embedding_table) {
    int seq_len = tokens.size();
    int hidden_dim = embedding_table.cols;

    Tensor result(seq_len, hidden_dim);

    for (int i = 0; i < seq_len; ++i) {
        int token_id = tokens[i];
        assert(token_id < embedding_table.rows && "Token ID tablo sinirini asiyor!");

        // İlgili kelimenin vektörünü satır satır Tensörümüze kopyalıyoruz
        for (int j = 0; j < hidden_dim; ++j) {
            result(i, j) = embedding_table(token_id, j);
        }
    }

    return result;
}