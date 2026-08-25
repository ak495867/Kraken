cmake_minimum_required(VERSION 3.20)
project(kraken_core LANGUAGES CXX)

find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)
find_package(pybind11 CONFIG REQUIRED)

option(KRAKEN_BUILD_BENCHMARKS "Build deterministic large-history native benchmarks" OFF)
include(CTest)

add_library(kraken_native STATIC
  cpp/numeric.cpp
  cpp/validation.cpp
  cpp/features.cpp
  cpp/sonar.cpp
  cpp/calibration.cpp
  cpp/regime.cpp
  cpp/dynamics.cpp
  cpp/config.cpp
  cpp/instrumentation.cpp
)
set_target_properties(kraken_native PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_include_directories(kraken_native PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/cpp/include)
target_compile_features(kraken_native PUBLIC cxx_std_17)

if(MSVC)
  target_compile_options(kraken_native PRIVATE /O2 /fp:strict)
else()
  target_compile_options(kraken_native PRIVATE -O3 -ffp-contract=off)
endif()

pybind11_add_module(_core cpp/bindings.cpp)
target_link_libraries(_core PRIVATE kraken_native)

if(BUILD_TESTING)
  add_executable(kraken_native_tests cpp/tests/native_tests.cpp)
  target_link_libraries(kraken_native_tests PRIVATE kraken_native)
  add_test(NAME kraken_native_tests COMMAND kraken_native_tests)
endif()

if(KRAKEN_BUILD_BENCHMARKS)
  add_executable(kraken_large_history_benchmark cpp/benchmarks/large_history_benchmark.cpp)
  target_link_libraries(kraken_large_history_benchmark PRIVATE kraken_native)
endif()

install(TARGETS _core LIBRARY DESTINATION kraken RUNTIME DESTINATION kraken ARCHIVE DESTINATION kraken)
