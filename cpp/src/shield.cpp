#include "omnicompass/shield.hpp"
#include <algorithm>
#include <cmath>
namespace omnicompass {
static bool is_expand(const std::string& k) { return k == "nodes" || k == "terraform_plan" || k == "rollout" || k == "replicas"; }
static bool is_infra(const std::string& k) { return k == "nodes" || k == "terraform_plan" || k == "rollout"; }

std::vector<std::string> violations(const std::vector<Action>& acts, const ShieldState& s, const ShieldLimits& lim) {
  std::vector<std::string> v;
  const int n = std::max(1, s.actual_nodes);
  const bool sec = s.security_block > 0.5;
  for (const auto& a : acts) {
    if (sec && a.direction > 0 && is_infra(a.kind)) v.push_back("I1");
    if (a.kind == "nodes") {
      const int t = static_cast<int>(a.target);
      const bool inside = s.min_nodes <= t && t <= s.max_nodes;
      const bool toward = (n > s.max_nodes && s.max_nodes <= t && t < n) || (n < s.min_nodes && n < t && t <= s.min_nodes);
      if (!inside && !toward) v.push_back("I2");
      const int add = t - n;
      if (std::abs(add) > lim.max_node_step) v.push_back("I5");
      if (add > 0 && s.power_stress * (n + add) / n > lim.power_limit) v.push_back("I4");
    }
    if (a.kind == "power_cap" && !(lim.cap_lo <= a.target && a.target <= lim.cap_hi)) v.push_back("I2");
  }
  bool up = false, tighten = false;
  for (const auto& a : acts) {
    up = up || (a.direction > 0 && is_expand(a.kind));
    tighten = tighten || (a.kind == "power_cap" && a.target < s.power_cap - 1e-9);
  }
  if (up && tighten) v.push_back("I3");
  return v;
}

ShieldResult enforce(const std::vector<Action>& acts, const ShieldState& s, const ShieldLimits& lim) {
  ShieldResult r;
  const int n = std::max(1, s.actual_nodes);
  const bool sec = s.security_block > 0.5;
  const double ps = s.power_stress;
  for (Action a : acts) {
    if (sec && a.direction > 0 && is_infra(a.kind)) { ++r.interventions; continue; }
    if (a.kind == "nodes") {
      const int r0 = static_cast<int>(a.target);
      const bool toward = (n > s.max_nodes && s.max_nodes <= r0 && r0 < n) || (n < s.min_nodes && n < r0 && r0 <= s.min_nodes);
      int t = toward ? r0 : std::max(s.min_nodes, std::min(s.max_nodes, r0));   // minimal intervention
      t = std::max(n - lim.max_node_step, std::min(n + lim.max_node_step, t));
      if (t > n && ps > 0.0) {
        const double k_max_d = std::min(1.0e6, (lim.power_limit / ps) * n - n + 1e-9);
        const int k_max = static_cast<int>(k_max_d);
        t = std::min(t, n + std::max(0, k_max));
      }
      if (sec && t > n) { ++r.interventions; continue; }   // I1 after clamping
      if (t != static_cast<int>(a.target)) ++r.interventions;
      if (t == n) continue;
      a.target = t; a.direction = t > n ? 1 : -1;
    }
    if (a.kind == "power_cap") {
      const double c = std::max(lim.cap_lo, std::min(lim.cap_hi, a.target));
      if (c != a.target) ++r.interventions;
      a.target = c;
    }
    r.actions.push_back(a);
  }
  bool up = false;
  for (const auto& a : r.actions) up = up || (a.direction > 0 && is_expand(a.kind));
  if (up) {
    std::vector<Action> kept;
    for (const auto& a : r.actions) {
      if (a.kind == "power_cap" && a.target < s.power_cap - 1e-9) { ++r.interventions; continue; }
      kept.push_back(a);
    }
    r.actions = kept;
  }
  return r;
}
}
