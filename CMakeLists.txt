cmake_minimum_required(VERSION 3.10)
project(PdfAiEngine)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# OpenMP desteğini bul (Çoklu çekirdek optimizasyonu)
find_package(OpenMP REQUIRED)

include_directories(include)

add_executable(AiEngine 
    src/main.cpp 
    src/tensor.cpp
    src/tokenizer.cpp
    src/pdf_layout.cpp
)

# OpenMP kütüphanelerini projeye bağla
if(OpenMP_CXX_FOUND)
    target_link_libraries(AiEngine PUBLIC OpenMP::OpenMP_CXX)
endif()