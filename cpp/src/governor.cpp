#include "omnicompass/governor.hpp"
#include <algorithm>
#include <cmath>
namespace omnicompass {
static double cl(double v, double lo, double hi) { return v < lo ? lo : (v > hi ? hi : v); }

Governor::Governor(AllocationLaw law, bool evolve) : L_(law), evolve_(evolve) {
  x_ = {0.12, 0.82, 0.0, 0.0, 0.0, 0.0};
  p_ = {4.2, 0.0, 0.0, 1.7, 0.38, 0.705, 1.35, 1.0, -0.40, 1.55, 1.15, 1.0, 2.0, 1.0, 2.5, 0.12, 0.10, 3.782, 3.487, 4.2, 0.719, 0.0};
}

Directive Governor::step(const Observation& ob, double current_cap, int nodes) {
  const double q = cl(ob.q, 0, 2), load = cl(ob.load, 0, 2), pw = cl(ob.power, 0, 1.5), th = cl(ob.thermal, 0, 1.5);
  const double nw = cl(ob.network, 0, 1.5), dr = cl(ob.drift, 0, 1.5), st = cl(ob.stale, 0, 1), sec = cl(ob.security, 0, 1);
  const double cf = cl(ob.conflicts / 4.0, 0, 1);
  const double e_obs = cl(0.25*q + 0.18*std::max(0.0, load-0.85) + 0.16*pw + 0.13*th + 0.10*nw + 0.08*dr + 0.06*cf + 0.04*st, 0, 1.5);
  const double u_obs = cl(1.0 - (0.27*q + 0.18*pw + 0.16*th + 0.12*nw + 0.12*dr + 0.10*cf + 0.05*st), 0, 1);
  const double s_obs = cl(0.36*th + 0.28*pw + 0.18*nw + 0.10*sec + 0.08*st - 0.20*q, -1, 1);
  const double b_obs = cl(0.52*pw + 0.26*th + 0.22*dr, -1, 1.5);
  const double i_obs = cl(q + dr + cf, 0, 2);
  const double a = 0.339;
  p_.beta_int = cl(0.58*q + 0.42*std::max(0.0, load-0.75), 0, 1);
  p_.beta_ext = cl(0.33*pw + 0.27*th + 0.20*nw + 0.12*st + 0.08*sec, 0, 1);
  const double U_before = x_.U;
  State xa{(1-a)*x_.E + a*e_obs, (1-a)*x_.U + a*u_obs, (1-a)*x_.I_U + a*i_obs,
           (1-a)*x_.S + a*s_obs, (1-a)*x_.B + a*b_obs, (1-a)*x_.B_dot + a*(b_obs - x_.B)};
  if (evolve_) {
    double t = t_;
    for (int i = 0; i < MICRO_STEPS; ++i) { xa = rk4_step(xa, p_, t, MICRO_DT, 0.0); t += MICRO_DT; }
  }
  x_ = xa; t_ += MACRO_DT;
  Directive d{}; d.x = x_;
  const int n = nodes;
  const double rho = cl(L_.rho0 - L_.kI*x_.I_U - L_.kE*x_.E, L_.rho_min, L_.rho0);
  const double load_sized = L_.size_at_full_cap ? load * current_cap : load;
  const long n_req = static_cast<long>(std::ceil(n * load_sized / rho)) + static_cast<long>(std::ceil(L_.kq * q * n));
  long delta = std::max<long>(-L_.down_max, std::min<long>(L_.up_max, n_req - n));
  const double drift_U = derivatives(x_, p_, t_, 0.0).U;
  const double u_push = std::max(-U_AUTHORITY, std::min(U_AUTHORITY, -drift_U + KP * (1.0 - x_.U)));
  const bool converged = u_push / U_AUTHORITY <= L_.push_release;
  if (delta < 0 && !converged) delta = 0;
  if (delta > 0 && q < L_.guard_queue && u_push / U_AUTHORITY < L_.push_add) delta = 0;
  if (delta < 0 && (q >= L_.guard_queue || n_req > n - L_.down_band)) delta = 0;
  surplus_streak_ = delta < 0 ? surplus_streak_ + 1 : 0;
  if (delta < 0 && (surplus_streak_ < L_.down_dwell || since_add_ < L_.down_after_add)) delta = 0;
  const double ceiling = q >= L_.guard_queue ? L_.power_ceiling_backlog : L_.power_ceiling;
  if (delta > 0 && (pw >= ceiling || n >= L_.max_nodes)) delta = 0;
  if (sec > 0.5) delta = std::min<long>(delta, 0);
  since_add_ = delta > 0 ? 0 : since_add_ + 1;
  if (delta < 0) surplus_streak_ = 0;
  const bool at_envelope = pw >= ceiling;
  double cap;
  if (q < L_.guard_queue && x_.U >= L_.U_gate) cap = cl(current_cap * load * (1.0 + L_.margin), L_.cap_min, 1.0);
  else if (q >= L_.guard_queue && L_.spread_step > 0.0)
    cap = at_envelope ? cl(current_cap - L_.spread_step, L_.cap_min, 1.0) : (L_.backlog_release ? 1.0 : (n < L_.max_nodes ? current_cap : 1.0));
  else cap = 1.0;
  cap = std::min(cap, cl(1.0 - L_.cap_gain * std::max(0.0, x_.B - L_.B_cap), L_.cap_min, 1.0));
  if (delta > 0) cap = std::max(cap, current_cap);
  d.command = cl(0.5 * (v_eff(x_, p_, 0.0) / std::max(p_.c, 1e-9) + 1.0), 0, 1);
  d.demand = rho;
  d.node_delta = static_cast<int>(delta);
  d.change_permitted = x_.U >= L_.U_gate && sec <= 0.5;
  d.power_cap = cap;
  d.rollback_authorized = x_.S >= L_.S_rollback || x_.U < U_before || sec > 0.5;
  d.route_shift = nw > L_.route_network;
  return d;
}
}
