// Reads an observation stream (CSV), runs one Governor per scenario, writes directives (CSV).
#include "omnicompass/governor.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>
using namespace omnicompass;
static std::vector<std::string> split(const std::string& s) { std::vector<std::string> v; std::stringstream ss(s); std::string x;
  while (std::getline(ss, x, ',')) { if (!x.empty() && x.back() == '\r') x.pop_back(); v.push_back(x); } return v; }
int main(int argc, char** argv) {
  if (argc != 3 && argc != 4) { std::cerr << "usage: oc_governor OBS.csv OUT.csv [power_protect|throughput]\n"; return 2; }
  AllocationLaw law{};
  if (argc == 4 && (std::string(argv[3]) == "throughput" || std::string(argv[3]).rfind("fleet", 0) == 0)) {
    law.backlog_release = true; law.power_ceiling = 9.0; law.power_ceiling_backlog = 9.0; law.spread_step = 0.0; law.B_cap = 9.0; law.size_at_full_cap = true;
    law.kI = 0.05; law.kE = 0.40; law.cap_min = 0.65; law.down_band = 1; law.down_dwell = 10; law.down_after_add = 3;
    law.kq = 0.30; law.U_gate = 0.45; law.push_release = 0.01;
  }
  if (argc == 4 && std::string(argv[3]).rfind("fleet", 0) == 0) {
    law.rho0 = 0.829; law.rho_min = 0.769; law.kI = 0.072; law.kE = 0.487; law.kq = 0.635; law.down_band = 3; law.down_dwell = 1; law.down_after_add = 5; law.push_release = 0.053; law.cap_min = 0.695; law.margin = 0.131; law.U_gate = 0.85; law.up_max = 8;
  }  if (argc == 4 && std::string(argv[3]) == "fleet_balanced") { law.push_release = 0.0098; law.push_add = 0.0098; }
  if (argc == 4 && std::string(argv[3]) == "fleet_wear") { law.push_release = 0.0035; law.push_add = 0.0035; }



  std::ifstream f(argv[1]); std::ofstream o(argv[2]); std::string line; std::getline(f, line);
  auto h = split(line); std::map<std::string, size_t> ix; for (size_t i = 0; i < h.size(); ++i) ix[h[i]] = i;
  o << "scenario_id,step,node_delta,change_permitted,power_cap,rollback_authorized,route_shift,demand,command,E,U,I_U,S,B\n";
  o << std::setprecision(17);
  std::map<int, Governor> govs; long n = 0;
  while (std::getline(f, line)) {
    if (line.empty()) continue;
    auto r = split(line);
    auto d = [&](const char* k) { return std::stod(r.at(ix.at(k))); };
    int sid = static_cast<int>(d("scenario_id"));
    Observation ob{d("q"), d("load"), d("power"), d("thermal"), d("network"), d("drift"), d("stale"), d("security"),
                   static_cast<int>(d("conflicts"))};
    auto it = govs.find(sid); if (it == govs.end()) it = govs.emplace(sid, Governor{law}).first;
    Directive dv = it->second.step(ob, d("current_cap"), static_cast<int>(d("nodes")));
    o << sid << ',' << r.at(ix.at("step")) << ',' << dv.node_delta << ',' << dv.change_permitted << ',' << dv.power_cap << ','
      << dv.rollback_authorized << ',' << dv.route_shift << ',' << dv.demand << ',' << dv.command << ','
      << dv.x.E << ',' << dv.x.U << ',' << dv.x.I_U << ',' << dv.x.S << ',' << dv.x.B << '\n';
    ++n;
  }
  std::cout << "processed " << n << " governor steps\n"; return 0;
}
