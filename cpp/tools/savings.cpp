// Savings projector: measured fractional energy reduction (from the benchmark) x a declared fleet profile.
// Output is a projection, not a measurement. Input CSV columns:
// profile,vessel,baseline,nodes,node_avg_kw,pue,usd_per_kwh,kg_co2_per_kwh,reduction_low,reduction_mid,reduction_high
#include <cstdio>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
int main(int argc, char** argv) {
  if (argc != 3) { std::cerr << "usage: oc_savings INPUTS.csv OUT.csv\n"; return 2; }
  std::ifstream f(argv[1]); std::ofstream o(argv[2]); std::string line; std::getline(f, line);
  o << "profile,vessel,baseline,baseline_mwh_per_year,saved_mwh_low,saved_mwh_mid,saved_mwh_high,"
       "saved_usd_low,saved_usd_mid,saved_usd_high,saved_tco2_low,saved_tco2_mid,saved_tco2_high\n";
  while (std::getline(f, line)) {
    if (line.empty()) continue;
    std::vector<std::string> c; std::stringstream ss(line); std::string x;
    while (std::getline(ss, x, ',')) c.push_back(x);
    const double nodes = std::stod(c[3]), kw = std::stod(c[4]), pue = std::stod(c[5]), usd = std::stod(c[6]), co2 = std::stod(c[7]);
    const double base_mwh = nodes * kw * pue * 8760.0 / 1000.0;
    char buf[512];
    std::snprintf(buf, sizeof buf, "%s,%s,%s,%.17g", c[0].c_str(), c[1].c_str(), c[2].c_str(), base_mwh);
    o << buf;
    for (int k = 0; k < 3; ++k) { std::snprintf(buf, sizeof buf, ",%.17g", base_mwh * std::stod(c[8 + k])); o << buf; }
    for (int k = 0; k < 3; ++k) { std::snprintf(buf, sizeof buf, ",%.17g", base_mwh * 1000.0 * usd * std::stod(c[8 + k])); o << buf; }
    for (int k = 0; k < 3; ++k) { std::snprintf(buf, sizeof buf, ",%.17g", base_mwh * co2 * std::stod(c[8 + k])); o << buf; }
    o << '\n';
  }
  return 0;
}
