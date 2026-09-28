// C++ twin of omnicompass/conveyance.py. Read the two side by side: every line here has its Python line.
#include "omnicompass/conveyance.hpp"
#include <algorithm>
#include <cmath>
namespace omnicompass {

static double sum(const std::vector<double>& v) { double s = 0.0; for (double x : v) s += x; return s; }

std::vector<double> deficits(const std::vector<double>& a, const std::vector<double>& d, double rho) {
  std::vector<double> e(a.size());
  for (size_t i = 0; i < a.size(); ++i) e[i] = d[i] / (rho * std::max(a[i], 1e-12)) - 1.0;
  return e;
}

std::vector<double> replicator_step(const std::vector<double>& a, const std::vector<double>& d, double rho, double kappa,
                                    double dt) {
  const double A = sum(a), D = sum(d);
  if (A <= 0 || D <= 0) return a;
  const double k = std::exp(-kappa * D * dt / (rho * A));
  std::vector<double> out(a.size());
  for (size_t i = 0; i < a.size(); ++i) out[i] = A * d[i] / D + (a[i] - A * d[i] / D) * k;
  return out;
}

std::vector<double> project(std::vector<double> a, const std::vector<double>& lo, const std::vector<double>& hi,
                            double budget) {
  const size_t n = a.size();
  for (size_t i = 0; i < n; ++i) a[i] = std::min(std::max(a[i], lo[i]), hi[i]);
  for (size_t round = 0; round < n + 1; ++round) {
    const double tot = sum(a);
    if (tot <= budget + 1e-9) return a;
    std::vector<char> free(n, 0);
    double share = 0.0;
    for (size_t i = 0; i < n; ++i) if (a[i] > lo[i] + 1e-12) { free[i] = 1; share += a[i] - lo[i]; }
    const double over = tot - budget;
    if (share <= 0) return a;
    std::vector<double> b(n);
    for (size_t i = 0; i < n; ++i) b[i] = free[i] ? std::max(lo[i], a[i] - over * (a[i] - lo[i]) / share) : a[i];
    a = b;
  }
  return a;
}

Conveyance::Conveyance(int n, double budget_, double rho_, double kappa_)
    : budget(budget_), rho(rho_), kappa(kappa_), a(n, budget_ / n), rate_(n, 0.0) {}

std::vector<double> Conveyance::step(const std::vector<double>& need_in, const std::vector<double>& lo_in,
                                     const std::vector<double>& hi_in) {
  const size_t n = need_in.size();
  // the living band: every organ keeps at least 5% of its range (idle, never off) and never takes more than 95%
  std::vector<double> lo(n), hi(n), need(n);
  for (size_t i = 0; i < n; ++i) lo[i] = std::max(lo_in[i], BAND_LO * hi_in[i]);
  for (size_t i = 0; i < n; ++i) hi[i] = std::max(lo[i], BAND_HI * hi_in[i]);
  for (size_t i = 0; i < n; ++i) need[i] = std::max(need_in[i], 1e-9);
  if (has_prev_)                                        // rate tracker for the reserve (the dual-bath rate channel)
    for (size_t i = 0; i < n; ++i) rate_[i] = 0.5 * rate_[i] + 0.5 * (need[i] - prev_[i]);
  prev_ = need; has_prev_ = true;
  double rise = 0.0; for (double r : rate_) rise += std::max(0.0, r);
  const double reserve = std::min(0.5 * budget, rise);
  std::vector<double> want(n);
  for (size_t i = 0; i < n; ++i) want[i] = std::max(std::min(hi[i], need[i] / rho), lo[i]);   // usable at rho, floored
  const double spend = std::max(sum(lo), std::min(budget - reserve, sum(want)));             // never spend unneeded budget
  std::vector<double> dneed(n);
  for (size_t i = 0; i < n; ++i) dneed[i] = want[i] * rho;
  std::vector<double> x = replicator_step(a, dneed, rho, kappa);
  const double sx = std::max(sum(x), 1e-12);
  for (size_t i = 0; i < n; ++i) x[i] = x[i] * spend / sx;
  std::vector<double> ceil(n);
  const bool enough = sum(want) <= spend;
  for (size_t i = 0; i < n; ++i) ceil[i] = enough ? std::max(lo[i], std::min(hi[i], want[i])) : hi[i];
  x = project(x, lo, ceil, spend);
  // surge (Ch. 30): release the reserve continuously to organs still in deficit, up to their ceiling
  const double left = budget - sum(x);
  std::vector<double> short_(n); double tot = 0.0;
  for (size_t i = 0; i < n; ++i) { short_[i] = std::max(0.0, std::min(hi[i], need[i] / rho) - x[i]); tot += short_[i]; }
  if (tot > 0 && left > 0)
    for (size_t i = 0; i < n; ++i) x[i] = x[i] + std::min(short_[i], left * short_[i] / tot);
  a = x;
  return a;
}
}
