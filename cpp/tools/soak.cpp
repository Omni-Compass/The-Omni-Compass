// Soak test: N consecutive governor decisions on randomized observations spanning and exceeding the sensor ranges.
// Reports state bounds, non-finite values, resident memory before and after, and time per decision.
#include "omnicompass/governor.hpp"
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <random>
#include <string>
using namespace omnicompass;
static long rss_kb() { std::ifstream f("/proc/self/statm"); long a = 0, b = 0; f >> a >> b; return b * 4; }
int main(int argc, char** argv) {
  const long long N = argc > 1 ? std::atoll(argv[1]) : 10000000LL;
  const bool throughput = argc > 2 && std::string(argv[2]) == "throughput";
  std::mt19937_64 r(20260923); std::uniform_real_distribution<double> u(-0.5, 2.5);
  AllocationLaw law{};
  if (throughput) {
    law.backlog_release = true; law.power_ceiling = 9.0; law.power_ceiling_backlog = 9.0; law.spread_step = 0.0; law.B_cap = 9.0;
    law.size_at_full_cap = true; law.kI = 0.05; law.kE = 0.40; law.cap_min = 0.65; law.down_band = 1; law.down_dwell = 10;
    law.down_after_add = 3; law.kq = 0.30; law.U_gate = 0.45; law.push_release = 0.01;
  }
  Governor g{law}; Observation o; long nonfinite = 0; long rss_cp[4] = {0, 0, 0, 0};
  double lo[5] = {1e300, 1e300, 1e300, 1e300, 1e300}, hi[5] = {-1e300, -1e300, -1e300, -1e300, -1e300};
  double cap = 1.0; int nodes = 20; const long rss0 = rss_kb();
  auto t0 = std::chrono::steady_clock::now();
  for (long long i = 0; i < N; ++i) {
    o.q = u(r); o.load = u(r); o.power = u(r); o.thermal = u(r); o.network = u(r); o.drift = u(r);
    o.stale = u(r) > 1.0; o.security = u(r) > 2.3; o.conflicts = static_cast<int>(i % 7);
    Directive d = g.step(o, cap, nodes);
    cap = d.power_cap; nodes = std::max(8, std::min(40, nodes + d.node_delta));
    const double v[5] = {d.x.E, d.x.U, d.x.I_U, d.x.S, d.x.B};
    for (int k = 0; k < 5; ++k) { if (!std::isfinite(v[k])) ++nonfinite; lo[k] = std::min(lo[k], v[k]); hi[k] = std::max(hi[k], v[k]); }
    if (!std::isfinite(d.power_cap) || d.power_cap < 0.0 || d.power_cap > 1.0) ++nonfinite;
    for (int c = 0; c < 4; ++c) if (i == (N / 4) * (c + 1) - 1) rss_cp[c] = rss_kb();
  }
  const double s = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  std::printf("{\"mode\": \"%s\", \"rss_kb_at_25_50_75_100pct\": [%ld, %ld, %ld, %ld], ", throughput ? "throughput" : "power_protect",
              rss_cp[0], rss_cp[1], rss_cp[2], rss_cp[3]);
  std::printf("\"decisions\": %lld, \"nonfinite_or_out_of_range\": %ld, \"rss_kb_start\": %ld, \"rss_kb_end\": %ld, "
              "\"ns_per_decision\": %.1f, \"years_at_5min_interval\": %.1f, "
              "\"E\": [%.6f, %.6f], \"U\": [%.6f, %.6f], \"I_U\": [%.6f, %.6f], \"S\": [%.6f, %.6f], \"B\": [%.6f, %.6f]}\n",
              N, nonfinite, rss0, rss_kb(), 1e9 * s / N, N * 5.0 / 60 / 24 / 365.25,
              lo[0], hi[0], lo[1], hi[1], lo[2], hi[2], lo[3], hi[3], lo[4], hi[4]);
  return nonfinite == 0 ? 0 : 1;
}
