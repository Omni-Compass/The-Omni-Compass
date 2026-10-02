// SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
// Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
// Omni-Compass Enterprise License. See LICENSE.
// Reads HPA step streams (CSV: stream,replicas0,min,max,metric,target), one Hpa per stream; writes replicas per step.
#include "omnicompass/hpa.hpp"
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>
using namespace omnicompass;
int main(int argc, char** argv) {
  if (argc != 3) { std::cerr << "usage: oc_hpa STEPS.csv OUT.csv\n"; return 2; }
  std::ifstream f(argv[1]); std::ofstream o(argv[2]); std::string line; std::getline(f, line);
  std::map<std::string, Hpa> h; long n = 0;
  o << "stream,replicas\n";
  while (std::getline(f, line)) {
    if (line.empty()) continue;
    std::vector<std::string> c; std::stringstream ss(line); std::string x;
    while (std::getline(ss, x, ',')) c.push_back(x);
    auto it = h.find(c[0]);
    if (it == h.end()) it = h.emplace(c[0], Hpa(std::stoi(c[1]), std::stoi(c[2]), std::stoi(c[3]))).first;
    o << c[0] << ',' << it->second.step(std::stod(c[4]), std::stod(c[5])) << '\n'; ++n;
  }
  std::cout << "processed " << n << " HPA steps\n";
  return 0;
}
