// Reads shield cases (CSV), applies enforce() and violations(), writes results (CSV).
#include "omnicompass/shield.hpp"
#include <cstdio>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
using namespace omnicompass;
static std::vector<std::string> split(const std::string& s, char d) {
  std::vector<std::string> v; std::stringstream ss(s); std::string x;
  while (std::getline(ss, x, d)) v.push_back(x);
  return v;
}
int main(int argc, char** argv) {
  if (argc != 3) { std::cerr << "usage: oc_shield CASES.csv OUT.csv\n"; return 2; }
  std::ifstream f(argv[1]); std::ofstream o(argv[2]); std::string line; std::getline(f, line);
  o << "case,interventions,enforced,violations\n";
  long n = 0;
  while (std::getline(f, line)) {
    if (line.empty()) continue;
    auto c = split(line, ',');
    ShieldState s{std::stoi(c[1]), std::stod(c[2]), std::stod(c[3]), std::stod(c[4]), std::stoi(c[5]), std::stoi(c[6])};
    ShieldLimits lim{}; lim.power_limit = std::stod(c[7]);
    std::vector<Action> acts;
    if (c.size() > 8 && !c[8].empty())
      for (const auto& a : split(c[8], ';')) { auto p = split(a, ':'); acts.push_back({p[0], std::stod(p[1]), std::stoi(p[2])}); }
    auto r = enforce(acts, s, lim);
    auto v = violations(acts, s, lim);
    o << c[0] << ',' << r.interventions << ',';
    for (size_t i = 0; i < r.actions.size(); ++i) {
      char buf[64]; std::snprintf(buf, sizeof buf, "%.17g", r.actions[i].target);
      o << (i ? ";" : "") << r.actions[i].kind << ':' << buf << ':' << r.actions[i].direction;
    }
    o << ',';
    for (size_t i = 0; i < v.size(); ++i) o << (i ? ";" : "") << v[i];
    o << '\n'; ++n;
  }
  std::cout << "processed " << n << " shield cases\n";
  return 0;
}
