#pragma once
#include <vector>
#include <iostream>
#include <string>

class Tensor {
public:
    int rows;
    int cols;
    std::vector<float> data;

    Tensor(int r, int c);

    float& operator()(int i, int j);
    const float& operator()(int i, int j) const;

    void print() const;

    // Matris Çarpımı: C = A x B
    static Tensor matmul(const Tensor& A, const Tensor& B);

    // Tam Bağlantılı Katman: Y = X * W + Bias
    static Tensor linear(const Tensor& input, const Tensor& weights, const Tensor& bias);

    // Matris Devriği (Transpose)
    Tensor transpose() const;

    // Satır Bazlı Softmax
    void softmax();

    // Aktivasyon: ReLU
    void relu();

    // İkili Dosya (Binary) İşlemleri
    void save_raw_binary(const std::string& filepath) const;
    static Tensor load_raw_binary(const std::string& filepath, int r, int c);

    // En yuksek olasilikli indeks (ArgMax)
    int argmax() const;
};