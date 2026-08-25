#include "kraken_core/numeric.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <stdexcept>

namespace kraken::detail {

bool is_finite(double value) {
  return std::isfinite(value);
}

double clamp(double value, double lower, double upper) {
  return std::max(lower, std::min(value, upper));
}

double mean(const std::vector<double>& values) {
  if (values.empty()) {
    throw std::invalid_argument("Cannot calculate a mean from an empty series");
  }
  return std::accumulate(values.begin(), values.end(), 0.0) / static_cast<double>(values.size());
}

double standard_deviation(const std::vector<double>& values) {
  if (values.size() < 2) {
    return kEpsilon;
  }
  const double average = mean(values);
  double squared_sum = 0.0;
  for (const double value : values) {
    const double delta = value - average;
    squared_sum += delta * delta;
  }
  return std::sqrt(squared_sum / static_cast<double>(values.size() - 1));
}

double quantile(std::vector<double> values, double probability) {
  if (values.empty() || !is_finite(probability) || probability < 0.0 || probability > 1.0) {
    throw std::invalid_argument("Quantile requires a non-empty finite series and probability within [0, 1]");
  }
  if (!std::all_of(values.begin(), values.end(), is_finite)) {
    throw std::invalid_argument("Quantile input must contain finite values");
  }
  const double position = probability * static_cast<double>(values.size() - 1);
  const auto lower = static_cast<std::size_t>(std::floor(position));
  const auto upper = static_cast<std::size_t>(std::ceil(position));
  auto lower_iterator = values.begin() + static_cast<std::ptrdiff_t>(lower);
  std::nth_element(values.begin(), lower_iterator, values.end());
  const double lower_value = *lower_iterator;
  if (lower == upper) {
    return lower_value;
  }
  auto upper_iterator = values.begin() + static_cast<std::ptrdiff_t>(upper);
  std::nth_element(values.begin(), upper_iterator, values.end());
  const double fraction = position - static_cast<double>(lower);
  return lower_value + fraction * (*upper_iterator - lower_value);
}

double correlation(const std::vector<double>& left, const std::vector<double>& right) {
  if (left.size() != right.size() || left.size() < 2) {
    return 0.0;
  }
  const double left_mean = mean(left);
  const double right_mean = mean(right);
  double numerator = 0.0;
  double left_square = 0.0;
  double right_square = 0.0;
  for (std::size_t index = 0; index < left.size(); ++index) {
    const double left_delta = left[index] - left_mean;
    const double right_delta = right[index] - right_mean;
    numerator += left_delta * right_delta;
    left_square += left_delta * left_delta;
    right_square += right_delta * right_delta;
  }
  return numerator / std::sqrt(std::max(left_square * right_square, kEpsilon));
}

}
