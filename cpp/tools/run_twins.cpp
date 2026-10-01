// oc_twins MODE IN.csv OUT.csv : feeds recorded inputs to a C++ twin and writes its outputs (17 significant digits),
// for the parity tests (tests/test_cpp_twins_parity.py). Modes:
//   nervous  rows E,U,I_U,S,push,push_release,U_gate,s_eq,security_block,slo_clean,power_stress,thermal,rollback,stale,autopilot,killed
//   gate     rows n,per_node_m,used_m,pending,scaling_up,breach,rho,may_contract,senses_live,landed
//   compass  first row E_max,alpha_s,beta_s,delta,use_state; rows E,S,l1,m1,l2,m2,forced[,E,U,I_U,S,B,B_dot,alpha_s,beta_s,delta,omega_B,Q_B,gamma_c,mu,alpha_E,lambda_I]
//   shield   rows cap,draw,start,min_w,headroom,min_share,slo_clean
//   busy     rows util,gate,band (one sequence; the state carries over)
//   lock     rows ratio,cur,start,min_w,since_last,speed_gain,lock_margin,lock_step,lock_boost,lock_floor,lock_hold_s
//   window   first row window_s; rows t,ms,ok (one window over all rows)
//   baseline first row k (bins); k rows rate,mean,p95,p99; then rows rate
#include "omnicompass/compass.hpp"
#include "omnicompass/gpu_rules.hpp"
#include "omnicompass/nervous_system.hpp"
#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
using namespace omnicompass;
static std::vector<double> row(const std::string& line) {
  std::stringstream ss(line); std::string f; std::vector<double> v;
  while (std::getline(ss, f, ',')) v.push_back(std::stod(f));
  return v;
}
struct Out {
  std::ofstream& o; bool first{true};
  void num(double x) { char b[40]; std::snprintf(b, sizeof b, first ? "%.17g" : ",%.17g", x); o << b; first = false; }
  void str(const std::string& s) { o << (first ? "" : ",") << s; first = false; }
  void end() { o << "\n"; first = true; }
};
int main(int argc, char** argv) {
  if (argc < 4) { std::fprintf(stderr, "usage: oc_twins MODE IN.csv OUT.csv\n"); return 2; }
  const std::string mode = argv[1];
  std::ifstream in(argv[2]); std::ofstream of(argv[3]); Out out{of}; std::string line;
  if (mode == "nervous") {
    while (std::getline(in, line)) {
      if (line.empty()) continue;
      const auto v = row(line);
      NervousInputs i{v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7], v[8], v[9] != 0, v[10], v[11], v[12] != 0, v[13], v[14] != 0, v[15] != 0};
      const Authority a = authority(i);
      out.num(a.execute); out.num(a.killed);
      if (!a.killed) {
        out.num(a.security_hold); out.num(a.scalars.kappa); out.num(a.scalars.h); out.num(a.scalars.sigma); out.num(a.scalars.nu); out.num(a.scalars.calm);
        for (const char* o : {"pods", "nodes", "cpufreq", "gpu", "power", "routing"}) {
          const Organ& g = a.organs.at(o); out.num(g.expand); out.num(g.contract); out.num(g.step);
        }
        for (const char* o : {"cpufreq", "gpu", "power", "routing"}) { out.num(a.organs.at(o).envelope[0]); out.num(a.organs.at(o).envelope[1]); }
        const Organ& c = a.organs.at("cooling"); out.num(c.contract); out.num(c.step); out.num(c.envelope[0]); out.num(c.envelope[1]);
        out.num(a.batch_admit); out.num(a.batch_pause); out.num(a.rollback_authorized);
        out.num(stress_equilibrium(v[3] + 0.5, 0.12, 0.10));
      }
      out.end();
    }
  } else if (mode == "gate") {
    while (std::getline(in, line)) {
      if (line.empty()) continue;
      const auto v = row(line);
      const ReleaseGate g = node_release_gate(int(v[0]), v[1], v[2], int(v[3]), v[4] != 0, v[5] != 0, v[6], v[7] != 0, v[8] != 0, v[9] != 0);
      out.num(g.ok); out.num(g.util_after); out.end();
    }
  } else if (mode == "compass") {
    std::getline(in, line); const auto h = row(line);
    Compass c(h[0], h[1], h[2], h[3]); const bool use_state = h[4] != 0;
    while (std::getline(in, line)) {
      if (line.empty()) continue;
      const auto v = row(line);
      std::map<std::string, double> lv{{"a", v[2]}, {"b", v[4]}}, mv{{"a", v[3]}, {"b", v[5]}};
      State x; Parameters p;
      if (use_state) {
        x = State{v[7], v[8], v[9], v[10], v[11], v[12]};
        p.alpha_s = v[13]; p.beta_s = v[14]; p.delta = v[15]; p.omega_B = v[16]; p.Q_B = v[17]; p.gamma_c = v[18];
        p.mu = v[19]; p.alpha_E = v[20]; p.lambda_I = v[21];
      }
      const Reading r = c.read(v[0], v[1], lv, mv, v[6] != 0, use_state ? &x : nullptr, use_state ? &p : nullptr);
      out.num(r.heading_deg); out.num(r.letter); out.num(r.point); out.num(r.quadrant); out.num(r.e); out.num(r.rate);
      out.num(r.axle_rest); out.num(r.ledger); out.num(r.has_step); out.num(r.ledger_step); out.num(r.descent);
      out.num(r.omega_held); out.num(r.inward_all); out.num(r.circles_closed); out.end();
    }
  } else if (mode == "shield") {
    while (std::getline(in, line)) {
      if (line.empty()) continue;
      const auto v = row(line);
      const Limit l = shield_limit(v[0], v[1], v[2], v[3], v[4], v[5], v[6] != 0);
      out.num(l.want); out.str(l.bound); out.end();
    }
  } else if (mode == "busy") {
    std::optional<double> u; bool gated = false;
    while (std::getline(in, line)) {
      if (line.empty()) continue;
      const auto v = row(line);
      const Gate g = busy_gate(u, v[0], gated, v[1], v[2]); u = g.u; gated = g.gated;
      out.num(g.u); out.num(g.gated); out.end();
    }
  } else if (mode == "lock") {
    while (std::getline(in, line)) {
      if (line.empty()) continue;
      const auto v = row(line);
      const LockStep s = lock_decide(v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7], v[8], v[9], v[10]);
      out.num(s.want); out.str(s.bound); out.num(s.line); out.num(s.aim); out.end();
    }
  } else if (mode == "window") {
    std::getline(in, line); const double w = row(line)[0]; std::vector<Row> rows;
    while (std::getline(in, line)) { if (line.empty()) continue; const auto v = row(line); rows.push_back({v[0], v[1], v[2] != 0}); }
    const auto s = window_stats(rows, w);
    if (!s) { out.str("none"); out.end(); }
    else { out.num(s->mean); out.num(s->p95); out.num(s->p99); out.num(s->rate); out.num(s->n); out.end(); }
  } else if (mode == "baseline") {
    std::getline(in, line); const int k = int(row(line)[0]); std::vector<BaselinePoint> bins;
    for (int i = 0; i < k; ++i) { std::getline(in, line); const auto v = row(line); bins.push_back({v[0], v[1], v[2], v[3]}); }
    while (std::getline(in, line)) {
      if (line.empty()) continue;
      const BaselinePoint b = baseline_at(bins, row(line)[0]);
      out.num(b.mean); out.num(b.p95); out.num(b.p99); out.end();
    }
  } else { std::fprintf(stderr, "unknown mode %s\n", mode.c_str()); return 2; }
  return 0;
}
