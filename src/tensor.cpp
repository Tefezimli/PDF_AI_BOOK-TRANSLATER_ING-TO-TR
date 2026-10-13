#include "tensor.h"
#include <iomanip>
#include <cassert>
#include <algorithm>
#include <cmath>
#include <fstream>

Tensor::Tensor(int r, int c) : rows(r), cols(c), data(r* c, 0.0f) {}

float& Tensor::operator()(int i, int j) {
    return data[i * cols + j];
}

const float& Tensor::operator()(int i, int j) const {
    return data[i * cols + j];
}

void Tensor::print() const {
    for (int i = 0; i < rows; ++i) {
        for (int j = 0; j < cols; ++j) {
            std::cout << std::setw(9) << std::setprecision(4) << (*this)(i, j) << " ";
        }
        std::cout << "\n";
    }
    std::cout << "------------------------------------\n";
}

Tensor Tensor::matmul(const Tensor& A, const Tensor& B) {
    assert(A.cols == B.rows && "Hata: Matris boyutlari carpim icin uyumsuz!");
    Tensor C(A.rows, B.cols);

    // İşlemcinin tüm çekirdeklerini bu döngü için seferber eden OpenMP komutu
#pragma omp parallel for
    for (int i = 0; i < A.rows; ++i) {
        for (int j = 0; j < B.cols; ++j) {
            float sum = 0.0f;
            for (int k = 0; k < A.cols; ++k) {
                sum += A(i, k) * B(k, j);
            }
            C(i, j) = sum;
        }
    }
    return C;
}

Tensor Tensor::linear(const Tensor& input, const Tensor& weights, const Tensor& bias) {
    Tensor out = matmul(input, weights);
    assert(out.cols == bias.cols && "Hata: Bias boyutu cikti sutun sayisiyla uyusmuyor!");

    for (int i = 0; i < out.rows; ++i) {
        for (int j = 0; j < out.cols; ++j) {
            out(i, j) += bias(0, j);
        }
    }
    return out;
}

Tensor Tensor::transpose() const {
    Tensor T(cols, rows);
    for (int i = 0; i < rows; ++i) {
        for (int j = 0; j < cols; ++j) {
            T(j, i) = (*this)(i, j);
        }
    }
    return T;
}

void Tensor::softmax() {
    for (int i = 0; i < rows; ++i) {
        float max_val = (*this)(i, 0);
        for (int j = 1; j < cols; ++j) {
            if ((*this)(i, j) > max_val) max_val = (*this)(i, j);
        }

        float sum_exp = 0.0f;
        for (int j = 0; j < cols; ++j) {
            (*this)(i, j) = std::exp((*this)(i, j) - max_val);
            sum_exp += (*this)(i, j);
        }

        for (int j = 0; j < cols; ++j) {
            (*this)(i, j) /= sum_exp;
        }
    }
}

void Tensor::relu() {
    for (float& val : data) {
        val = std::max(0.0f, val);
    }
}

void Tensor::save_raw_binary(const std::string& filepath) const {
    std::ofstream out(filepath, std::ios::binary);
    assert(out.is_open() && "Hata: Agirlik dosyasi yazmak icin acilamadi!");
    out.write(reinterpret_cast<const char*>(data.data()), data.size() * sizeof(float));
    out.close();
}

Tensor Tensor::load_raw_binary(const std::string& filepath, int r, int c) {
    Tensor loaded(r, c);
    std::ifstream in(filepath, std::ios::binary);
    assert(in.is_open() && "Hata: Agirlik dosyasi okumak icin bulunamadi!");
    in.read(reinterpret_cast<char*>(loaded.data.data()), loaded.data.size() * sizeof(float));
    in.close();
    return loaded;
}

int Tensor::argmax() const {
    int best_idx = 0;
    float max_val = data[0];
    for (size_t i = 1; i < data.size(); ++i) {
        if (data[i] > max_val) {
            max_val = data[i];
            best_idx = i;
        }
    }
    return best_idx;
}