#pragma once

#include "kraken_core/types.hpp"

#include <cstdint>
#include <vector>

namespace kraken::detail {

std::vector<Bar> eligible(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms);
void require_valid(const IntegrityReport& report);

}
