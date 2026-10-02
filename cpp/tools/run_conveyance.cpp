// SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
// Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
// Omni-Compass Enterprise License. See LICENSE.
// oc_conveyance IN.csv OUT.csv : first row "n,budget,rho,kappa"; then per step 3n values "need..., lo..., hi...";
// writes per step the n allocations from the C++ conveyance law (17 significant digits).
#include "omnicompass/conveyance.hpp"
#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>
using namespace omnicompass;
static std::vector<double> row(const std::string& line) {
  std::stringstream ss(line); std::string f; std::vector<double> v;
  while (std::getline(ss, f, ',')) v.push_back(std::stod(f));
  return v;
}
int main(int argc, char** argv) {
  if (argc < 3) { std::fprintf(stderr, "usage: oc_conveyance IN.csv OUT.csv\n"); return 2; }
  std::ifstream in(argv[1]); std::ofstream out(argv[2]); std::string line;
  std::getline(in, line); const std::vector<double> h = row(line);
  const int n = int(h[0]);
  Conveyance cv(n, h[1], h[2], h[3]);
  char buf[40];
  while (std::getline(in, line)) {
    if (line.empty()) continue;
    const std::vector<double> v = row(line);
    std::vector<double> need(v.begin(), v.begin() + n), lo(v.begin() + n, v.begin() + 2 * n), hi(v.begin() + 2 * n, v.begin() + 3 * n);
    const std::vector<double> a = cv.step(need, lo, hi);
    for (int i = 0; i < n; ++i) { std::snprintf(buf, sizeof buf, i ? ",%.17g" : "%.17g", a[i]); out << buf; }
    out << "\n";
  }
  return 0;
}
