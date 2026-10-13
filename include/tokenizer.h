#pragma once
#include <string>
#include <vector>
#include <unordered_map>
#include "tensor.h"

class Tokenizer {
public:
    std::unordered_map<std::string, int> vocab_to_id;
    std::unordered_map<int, std::string> id_to_vocab;
    int vocab_size;

    Tokenizer();

    // Kelime dağarcığına yeni kelime ekleme
    void add_word(const std::string& word);

    // Cümleyi Token ID listesine çevirme (Encode)
    std::vector<int> encode(const std::string& text) const;

    // Token ID listesini tekrar cümleye çevirme (Decode)
    std::string decode(const std::vector<int>& tokens) const;

    // Token ID'leri Embedding tablosundan okuyup Tensör üretme
    static Tensor get_embeddings(const std::vector<int>& tokens, const Tensor& embedding_table);
};