// SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
// Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
// Omni-Compass Enterprise License. See LICENSE.
// oc_closure LAW.csv TRACE.csv OUT.csv : law parameters (one row), then per tick "r,n,c,push,n_min,n_max";
// writes per tick "target,reserve" from the C++ closure law.
#include "omnicompass/closure.hpp"
#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>
using namespace omnicompass;
int main(int argc, char** argv) {
  if (argc < 4) { std::fprintf(stderr, "usage: oc_closure LAW.csv TRACE.csv OUT.csv\n"); return 2; }
  std::ifstream lf(argv[1]); std::string line; std::getline(lf, line); std::getline(lf, line);
  std::stringstream ls(line); std::string f; std::vector<double> v;
  while (std::getline(ls, f, ',')) v.push_back(std::stod(f));
  ClosureLaw L; L.rho_max = v[0]; L.delta = v[1]; L.H_add = int(v[2]); L.H_rel = int(v[3]); L.a = v[4]; L.b = v[5]; L.g = v[6];
  L.push_release = v[7]; L.turn = v[8] != 0; L.delta_rel = v[9]; L.z = v[10]; L.tone = v[11] != 0; L.tone_H = int(v[12]); L.dwell = int(v[13]);
  ClosureNodes nodes(L);
  std::ifstream tf(argv[2]); std::ofstream out(argv[3]); std::getline(tf, line); out << "target,reserve\n";
  char buf[64];
  while (std::getline(tf, line)) {
    std::stringstream ss(line); std::vector<double> x;
    while (std::getline(ss, f, ',')) x.push_back(std::stod(f));
    nodes.observe(x[0]);
    const int t = nodes.decide(int(x[1]), x[2], x[3], int(x[4]), int(x[5]));
    std::snprintf(buf, sizeof buf, "%d,%d\n", t, nodes.reserve(x[2])); out << buf;
  }
  return 0;
}
