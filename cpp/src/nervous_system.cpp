// C++ twin of omnicompass/nervous_system.py. Read the two side by side: every line here has its Python line.
#include "omnicompass/nervous_system.hpp"
#include "omnicompass/conveyance.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
namespace omnicompass {

static double clamp(double x, double lo, double hi) { return x < lo ? lo : (x > hi ? hi : x); }

double stress_equilibrium(double delta, double alpha_s, double beta_s) {
  const double qa = 0.75 * beta_s;
  return qa > 0 ? (-alpha_s + std::sqrt(alpha_s * alpha_s + 4.0 * qa * delta)) / (2.0 * qa) : delta / alpha_s;
}

std::array<double, 2> in_band(double lo, double hi) {
  const double h = std::min(BAND_HI, std::max(BAND_LO, hi));
  return {std::min(h, std::max(BAND_LO, lo)), h};
}

Scalars scalars(const NervousInputs& i) {
  Scalars s;
  s.kappa = i.push <= i.push_release ? 1.0 : i.push_release / std::max(i.push, 1e-12);
  s.h = clamp((i.U - i.U_gate) / std::max(1.0 - i.U_gate, 1e-12), 0.0, 1.0);
  s.sigma = i.s_eq > 0 ? i.S / i.s_eq : 0.0;
  s.nu = std::max(0.0, i.I_U);
  const double calm = s.kappa * s.h * (1.0 - clamp(s.sigma - 1.0, 0.0, 1.0)) * (1.0 - clamp(s.nu, 0.0, 1.0));
  s.calm = clamp(calm, 0.0, 1.0);
  return s;
}

Authority authority(const NervousInputs& i) {
  Authority a;
  if (i.killed) { a.execute = false; a.killed = true; return a; }
  a.scalars = scalars(i); const double calm = a.scalars.calm;
  const bool sec = i.security_block > 0.5;
  const bool hot = i.thermal >= 0.96;
  const double excess = clamp(i.thermal - 0.96, 0.0, 1.0);
  const bool seeing = i.stale <= 0.0;       // never give capacity back on a blind sense; expanding stays allowed
  static const std::pair<const char*, double> THETA[] = {{"pods", 0.5}, {"nodes", 0.7}, {"cpufreq", 0.3},
                                                          {"gpu", 0.3}, {"power", 0.3}, {"routing", 0.5}};
  for (const auto& [o, th] : THETA) {
    const bool ok = calm >= th && i.slo_clean && seeing;
    a.organs[o] = Organ{!sec, ok, ok ? calm : 0.0};
  }
  const double cf_lo = 1.0 - 0.35 * calm, gp_lo = 1.0 - 0.30 * calm;
  const double cf_hi = hot ? 1.0 - 0.35 * excess : 1.0, gp_hi = hot ? 1.0 - 0.35 * excess : 1.0;
  a.organs["cpufreq"].envelope = in_band(std::min(cf_lo, cf_hi), cf_hi); a.organs["cpufreq"].has_envelope = true;
  a.organs["gpu"].envelope = in_band(std::min(gp_lo, gp_hi), gp_hi); a.organs["gpu"].has_envelope = true;
  a.organs["power"].envelope = in_band(0.65, 1.0); a.organs["power"].has_envelope = true;
  // routing is an amount moved, not a level: it may move nothing, never more than the band's top
  a.organs["routing"].envelope = {0.0, !sec ? std::min(BAND_HI, 0.5 * calm) : 0.0}; a.organs["routing"].has_envelope = true;
  a.organs["cooling"] = Organ{true, calm >= 0.3 && seeing, calm, {18.0, 18.0 + 9.0 * calm}, true};
  a.batch_admit = (!sec) && seeing && calm >= 0.5 && i.power_stress < 0.9;
  a.batch_pause = a.scalars.sigma > 1.0 || i.power_stress >= 0.95 || hot;
  a.rollback_authorized = i.rollback || sec;
  a.execute = i.autopilot; a.killed = false; a.security_hold = sec;
  return a;
}

ReleaseGate node_release_gate(int n, double per_node_m, double used_m, int pending, bool pods_scaling_up,
                              bool latency_breach_now, double rho, bool node_may_contract, bool senses_live,
                              bool last_command_landed) {
  ReleaseGate r;
  r.util_after = n > 1 ? used_m / std::max((n - 1) * per_node_m, 1e-9) : std::numeric_limits<double>::infinity();
  r.ok = n > 1 && pending == 0 && !pods_scaling_up && !latency_breach_now && r.util_after <= rho && node_may_contract &&
         senses_live && last_command_landed;
  return r;
}
}
