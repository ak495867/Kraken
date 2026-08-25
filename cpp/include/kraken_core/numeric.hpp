#pragma once

#include <vector>

namespace kraken::detail {

inline constexpr double kEpsilon = 1e-12;

bool is_finite(double value);
double clamp(double value, double lower, double upper);
double mean(const std::vector<double>& values);
double standard_deviation(const std::vector<double>& values);
double quantile(std::vector<double> values, double probability);
double correlation(const std::vector<double>& left, const std::vector<double>& right);

}
