// Closure law (C++ twin of omnicompass/closure.py ClosureLaw / ClosureNodes): same arithmetic, same order of operations.
#pragma once
#include <vector>
namespace omnicompass {
struct ClosureLaw {
  double rho_max{0.95}, delta{0.05}; int H_add{8}, H_rel{40};
  double a{0.5}, b{0.1}, g{0.05}, push_release{0.2}; bool turn{true};
  double delta_rel{-1.0}, z{0.0}; bool tone{false}; int tone_H{960}; int dwell{0};
};
class ClosureNodes {
 public:
  explicit ClosureNodes(const ClosureLaw& law) : law_(law) {}
  void observe(double r, double dt = 1.0);
  double fwd_max(int H) const;
  int reserve(double c) const;
  int decide(int n, double c, double push, int n_min, int n_max);
 private:
  ClosureLaw law_; bool has_{false}; double L_{0.0}, v_{0.0}, s2_{0.0}; int calm_{0};
  std::vector<double> hist_;
};
}
