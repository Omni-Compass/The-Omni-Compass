// Conveyance law (C++ twin of omnicompass/conveyance.py): a conserved budget moved between organs by need.
// Same arithmetic, same order of operations: replicator_step (the exact closed form of the replicator flow), project
// (water-filling onto floors, ceilings and the budget), and Conveyance::step (living band, reserve, flow, projection,
// continuous release of the reserve). Proofs: docs/CONVEYANCE_LAW.md.
#pragma once
#include <vector>
namespace omnicompass {
inline constexpr double BAND_LO = 0.05, BAND_HI = 0.95;   // the living band (omnicompass/nervous_system.py BAND)
std::vector<double> deficits(const std::vector<double>& a, const std::vector<double>& d, double rho);
std::vector<double> replicator_step(const std::vector<double>& a, const std::vector<double>& d, double rho, double kappa,
                                    double dt = 1.0);
std::vector<double> project(std::vector<double> a, const std::vector<double>& lo, const std::vector<double>& hi,
                            double budget);
class Conveyance {
 public:
  Conveyance(int n, double budget, double rho = 0.8, double kappa = 1.0);
  std::vector<double> step(const std::vector<double>& need, const std::vector<double>& lo, const std::vector<double>& hi);
  double budget, rho, kappa;
  std::vector<double> a;
 private:
  std::vector<double> prev_, rate_;
  bool has_prev_{false};
};
}
