// The compass (C++ twin of omnicompass/compass.py) and the engine's composite storage, the ledger that closes the
// circle (C++ twin of omnicompass/storage.py). Same arithmetic, same order of operations.
#pragma once
#include "omnicompass/core.hpp"
#include <map>
#include <optional>
#include <string>
namespace omnicompass {
// storage.py
double phi_engine(double S, const Parameters& p);                 // core.phi: basin potential, equation (5)
double stable_S(const Parameters& p);                              // S*, the stable rest of the axle
struct CompositeV { double V{}, V_U{}, V_W{}, V_E{}, V_S{}, V_I{}, V_B{}, S_star{}, B_star{}; };
CompositeV composite_V(const State& x, const Parameters& p, int sigma = 1);
// compass.py
double phi_compass(double S, double alpha_s, double beta_s, double delta);
double axle(double alpha_s, double beta_s, double delta);
double heading(double e, double rate);
int quadrant(double e, double rate);
bool inward(double level, double move, double eps = 0.01);
struct Reading {
  double heading_deg{}; int letter{}, point{}, quadrant{}; double e{}, rate{}, axle_rest{}, ledger{};
  bool has_step{}; double ledger_step{}; bool descent{}, omega_held{}, inward_all{}; int circles_closed{};
};
class Compass {
 public:
  Compass(double E_max = 1.0, double alpha_s = 0.12, double beta_s = 0.10, double delta = 0.5)
      : E_max_(E_max), alpha_s_(alpha_s), beta_s_(beta_s), delta_(delta) {}
  Reading read(double E, double S, const std::map<std::string, double>& levels = {},
               const std::map<std::string, double>& moves = {}, bool forced = false,
               const State* x = nullptr, const Parameters* p = nullptr);
 private:
  double E_max_, alpha_s_, beta_s_, delta_;
  std::optional<double> prev_e_, prev_L_; double scale_{0.0}; int turns_{0}; std::optional<int> last_q_;
};
}
