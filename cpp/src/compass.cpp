// C++ twin of omnicompass/compass.py and omnicompass/storage.py. Every line here has its Python line.
#include "omnicompass/compass.hpp"
#include "omnicompass/conveyance.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>
namespace omnicompass {

static constexpr double PI = 3.14159265358979323846;

// ---- storage.py -------------------------------------------------------------------------------------------------
double phi_engine(double S, const Parameters& p) { return 0.5 * p.alpha_s * S * S + 0.25 * p.beta_s * std::pow(S, 3.0) - p.delta * S; }

double stable_S(const Parameters& p) {
  const double a = 0.75 * p.beta_s, b = p.alpha_s, c = -p.delta;
  if (std::abs(a) <= EPS) return p.delta / std::max(p.alpha_s, EPS);
  const double disc = std::max(0.0, b * b - 4.0 * a * c);
  for (double r : {(-b + std::sqrt(disc)) / (2.0 * a), (-b - std::sqrt(disc)) / (2.0 * a)})
    if (-p.alpha_s - 1.5 * p.beta_s * r < 0.0) return r;
  throw std::runtime_error("no stable S rest point");
}

static void bath_P(const Parameters& p, double& p11, double& p12, double& p22) {
  const double w = std::max(std::abs(p.omega_B), EPS);
  const double damp = std::max(w / std::max(std::abs(p.Q_B), EPS), EPS);
  p12 = 1.0 / (2.0 * w * w); p22 = (p12 + 0.5) / damp; p11 = damp * p12 + w * w * p22;
}

CompositeV composite_V(const State& x, const Parameters& p, int sigma) {
  const double sig = sigma >= 0 ? 1.0 : -1.0;
  const double alpha_s = std::max(p.alpha_s, EPS), beta_s = std::max(p.beta_s, EPS);
  double p11, p12, p22; bath_P(p, p11, p12, p22);
  const double g = p.gamma_c * p.delta;
  const double pg0 = p12 * g, pg1 = p22 * g;
  const double m_floor = alpha_s / 2.0;
  const double a_U = 1.0, b_W = 1.0 / (2.0 * std::max(p.mu, EPS)), c_E = 1.0 / std::max(p.alpha_E, EPS);
  const double w_I = 1.0 / std::max(p.lambda_I, EPS), w_S = (std::pow(pg0, 2.0) + std::pow(pg1, 2.0) + 0.25) / (m_floor * m_floor), d_B = 1.0;
  (void)beta_s;
  const double s_star = stable_S(p);
  const double ob = std::max(std::abs(p.omega_B), EPS);
  const double b_star = p.gamma_c * p.delta / std::pow(ob, 2.0) * s_star;
  const double z0 = x.B - b_star, z1 = x.B_dot;
  CompositeV v;
  v.V_U = 0.5 * a_U * std::pow(x.U - sig, 2.0);
  v.V_W = b_W * 0.25 * p.mu * std::pow(x.U * x.U - 1.0, 2.0);
  v.V_E = 0.5 * c_E * std::pow(x.E, 2.0);
  v.V_S = w_S * (phi_engine(x.S, p) - phi_engine(s_star, p));
  v.V_I = 0.5 * w_I * std::pow(x.I_U, 2.0);
  v.V_B = 0.5 * d_B * (p11 * z0 * z0 + 2 * p12 * z0 * z1 + p22 * z1 * z1);
  v.V = v.V_U + v.V_W + v.V_E + v.V_S + v.V_I + v.V_B;
  v.S_star = s_star; v.B_star = b_star;
  return v;
}

// ---- compass.py -------------------------------------------------------------------------------------------------
double phi_compass(double S, double alpha_s, double beta_s, double delta) {
  return alpha_s * S * S / 2.0 + beta_s * std::pow(S, 3.0) / 4.0 - delta * S;
}

double axle(double alpha_s, double beta_s, double delta) {
  const double q = 0.75 * beta_s;
  if (q <= 0) return alpha_s > 0 ? delta / alpha_s : 0.0;
  return (-alpha_s + std::sqrt(alpha_s * alpha_s + 4.0 * q * delta)) / (2.0 * q);
}

double heading(double e, double rate) {
  if (std::abs(e) < 1e-12 && std::abs(rate) < 1e-12) return 0.0;
  double h = std::fmod(std::atan2(e, rate) * (180.0 / PI), 360.0);
  if (h < 0) h += 360.0;
  return h;
}

int quadrant(double e, double rate) {
  if (e > 0) return rate > 0 ? 1 : 2;
  return rate < 0 ? 3 : 4;
}

bool inward(double level, double move, double eps) {
  if (level >= BAND_HI - eps && move > 0) return false;
  if (level <= BAND_LO + eps && move < 0) return false;
  return true;
}

static double pymod(double a, double m) { double r = std::fmod(a, m); return r < 0 ? r + m : r; }

Reading Compass::read(double E, double S, const std::map<std::string, double>& levels,
                      const std::map<std::string, double>& moves, bool forced, const State* x, const Parameters* p) {
  const double e = E / std::max(E_max_, 1e-12);
  const double raw = prev_e_ ? e - *prev_e_ : 0.0;
  scale_ = scale_ == 0.0 ? raw * raw : 0.9 * scale_ + 0.1 * raw * raw;
  const double rate = scale_ > 1e-18 ? raw / std::sqrt(scale_) : 0.0;
  Reading r;
  const double h = heading(e, rate);
  const int q = quadrant(e, rate);
  if (last_q_ && *last_q_ == 4 && q == 1) ++turns_;
  r.point = int(pymod(h + 22.5, 360.0) / 45.0);
  r.letter = int(pymod(h + 7.5, 360.0) / 15.0);
  double s_star = axle(alpha_s_, beta_s_, delta_), L;
  if (x && p) {
    const CompositeV cv = composite_V(*x, *p, 1);
    L = cv.V; s_star = cv.S_star;
  } else {
    L = 0.5 * e * e + phi_compass(S, alpha_s_, beta_s_, delta_) - phi_compass(s_star, alpha_s_, beta_s_, delta_);
  }
  bool held = true, inw = true;
  for (const auto& [k, v] : levels) {
    if (!(BAND_LO - 1e-9 <= v && v <= BAND_HI + 1e-9)) held = false;
    const auto it = moves.find(k);
    if (!inward(v, it == moves.end() ? 0.0 : it->second)) inw = false;
  }
  r.heading_deg = h; r.quadrant = q; r.e = e; r.rate = rate; r.axle_rest = s_star; r.ledger = L;
  r.has_step = prev_L_.has_value(); r.ledger_step = r.has_step ? L - *prev_L_ : 0.0;
  r.descent = r.has_step && (r.ledger_step <= 1e-9 || forced);
  r.omega_held = held; r.inward_all = inw; r.circles_closed = turns_;
  prev_e_ = e; prev_L_ = L; last_q_ = q;
  return r;
}
}
