#pragma once
// Omni-Compass stack governor: sense -> assimilate -> canonical bounded FF+P evolve -> allocate.
#include "omnicompass/core.hpp"
namespace omnicompass {
struct Observation { double q{}, load{}, power{}, thermal{}, network{}, drift{}, stale{}, security{}; int conflicts{}; };
struct AllocationLaw {
  double rho0{0.914}, rho_min{0.627}, kI{0.252}, kE{0.297}, kq{0.795}; int up_max{2}, down_max{1};
  double guard_queue{0.05}, power_ceiling{0.95}, power_ceiling_backlog{1.00}, spread_step{0.05}; bool backlog_release{false}, size_at_full_cap{false}; double push_release{0.005}, push_add{-9.0}; double U_gate{0.481}, margin{0.006}, cap_min{0.706}, B_cap{0.40}, cap_gain{0.60};
  double S_rollback{0.55}; double route_network{0.20}; int down_band{4}, down_dwell{4}, down_after_add{4}; int min_nodes{8}, max_nodes{40};
  double disrupt_budget_pct{10.0}; int disrupt_budget_abs{0}, disrupt_window_steps{60}; bool disrupt_when_empty_only{false};
};
struct Directive { int node_delta{}; bool change_permitted{}, rollback_authorized{}, route_shift{};
                   double power_cap{}, demand{}, command{}, u_hold{}; State x{}; };
class Governor {
 public:
  explicit Governor(AllocationLaw law = {}, bool evolve = true);
  Directive step(const Observation& obs, double current_cap, int nodes);
  const State& state() const noexcept { return x_; }
 private:
  AllocationLaw L_; bool evolve_; State x_; Parameters p_; double t_{0.0}; int target_sign_{1}; int surplus_streak_{0}, since_add_{99};
  int disrupt_window_left_{0}, disrupt_used_{0}, disrupt_window_n0_{0};
};
}
