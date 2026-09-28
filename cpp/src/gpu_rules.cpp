// C++ twin of the GPU governor's rules (omni_controller/gpu_governor.py: shield_limit, busy_gate, lock_decide,
// baseline_at, window_stats). Every line here has its Python line.
#include "omnicompass/gpu_rules.hpp"
#include <algorithm>
#include <cmath>
namespace omnicompass {

Limit shield_limit(double cap, double draw, double start, double min_w, double headroom, double min_share, bool slo_clean) {
  const double share_floor = min_share * start;
  const double floor_ = std::max({draw * (1.0 + headroom), min_w, share_floor});
  const double engine_w = std::floor(cap * start);
  const int want = int(std::min(start, std::max(engine_w, std::ceil(floor_))));
  std::string bound;
  if (!slo_clean) bound = "slo_or_blind_reflex";
  else if (want >= start && engine_w >= start) bound = "start_ceiling";
  else if (std::ceil(floor_) > engine_w && floor_ == share_floor) bound = "share_floor";
  else if (std::ceil(floor_) > engine_w && floor_ > min_w) bound = "draw_headroom_floor";
  else if (std::ceil(floor_) > engine_w) bound = "device_minimum";
  else bound = "engine";
  return {want, bound};
}

Gate busy_gate(std::optional<double> u_prev, double util, bool gated_prev, double gate, double band) {
  const double u = 0.5 * (u_prev ? *u_prev : util) + 0.5 * util;
  return {u, u >= gate || (gated_prev && u >= gate - band)};
}

LockStep lock_decide(double ratio, double cur, double start, double min_w, double since_last, double speed_gain,
                     double lock_margin, double lock_step, double lock_boost, double lock_floor, double lock_hold_s) {
  const double line = 1.0 - speed_gain;
  const double aim = line * (1.0 - lock_margin);
  const double floor_ = std::max(min_w, lock_floor * start);
  double want; std::string bound;
  if (ratio > line) { want = start; bound = "speed_lock_release"; }
  else if (ratio < aim && since_last >= lock_hold_s) {
    const double mult = std::min(lock_boost, std::max(1.0, (aim - ratio) / std::max(1e-6, line * lock_margin)));
    want = std::max(floor_, cur - mult * lock_step * start); bound = "speed_lock_spend";
  } else { want = cur; bound = "speed_lock_hold"; }
  return {int(std::min(start, std::max(floor_, want))), bound, line, aim};
}

BaselinePoint baseline_at(const std::vector<BaselinePoint>& bins, double rate) {
  if (rate <= bins.front().rate) return bins.front();
  if (rate >= bins.back().rate) return bins.back();
  for (size_t i = 0; i + 1 < bins.size(); ++i) {
    const BaselinePoint& lo = bins[i]; const BaselinePoint& hi = bins[i + 1];
    if (lo.rate <= rate && rate <= hi.rate) {
      const double f = (rate - lo.rate) / (hi.rate - lo.rate);
      return {rate, lo.mean + f * (hi.mean - lo.mean), lo.p95 + f * (hi.p95 - lo.p95), lo.p99 + f * (hi.p99 - lo.p99)};
    }
  }
  return bins.back();
}

std::optional<WindowStats> window_stats(const std::vector<Row>& rows, double window_s) {
  if (rows.empty()) return std::nullopt;
  const double t_end = rows.back().t;
  std::vector<double> ms;
  for (const Row& r : rows) if (r.t >= t_end - window_s && r.ok) ms.push_back(r.ms);
  if (ms.size() < 20) return std::nullopt;
  std::sort(ms.begin(), ms.end());
  const double span = std::min(window_s, std::max(1.0, t_end - rows.front().t));
  double s = 0.0; for (double m : ms) s += m;
  const size_t n = ms.size();
  WindowStats w;
  w.mean = s / double(n);
  w.p95 = ms[std::min(n - 1, size_t(0.95 * double(n)))];
  w.p99 = ms[std::min(n - 1, size_t(0.99 * double(n)))];
  w.rate = double(n) / span; w.n = int(n);
  return w;
}
}
