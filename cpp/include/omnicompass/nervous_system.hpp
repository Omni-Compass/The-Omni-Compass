// Nervous system (C++ twin of omnicompass/nervous_system.py): one engine state grants authority to every organ.
// Same arithmetic, same order of operations. The living band [0.05, 0.95] is applied last to every envelope.
#pragma once
#include <array>
#include <map>
#include <string>
namespace omnicompass {
double stress_equilibrium(double delta, double alpha_s, double beta_s);   // omnicompass/closure.py, equation (6)
std::array<double, 2> in_band(double lo, double hi);
struct NervousInputs {
  double E{}, U{}, I_U{}, S{}, push{}, push_release{0.2}, U_gate{0.5}, s_eq{1.0};
  double security_block{0.0}; bool slo_clean{true}; double power_stress{0.0}, thermal{0.0};
  bool rollback{false}; double stale{0.0}; bool autopilot{true}; bool killed{false};
};
struct Scalars { double kappa{}, h{}, sigma{}, nu{}, calm{}; };
struct Organ { bool expand{}, contract{}; double step{}; std::array<double, 2> envelope{0.0, 0.0}; bool has_envelope{false}; };
struct Authority {
  bool execute{}, killed{}, security_hold{};
  Scalars scalars{};
  std::map<std::string, Organ> organs;          // pods, nodes, cpufreq, gpu, power, routing, cooling
  bool batch_admit{}, batch_pause{}, rollback_authorized{};
};
Scalars scalars(const NervousInputs& i);
Authority authority(const NervousInputs& i);
struct ReleaseGate { bool ok{}; double util_after{}; };
ReleaseGate node_release_gate(int n, double per_node_m, double used_m, int pending, bool pods_scaling_up,
                              bool latency_breach_now, double rho, bool node_may_contract, bool senses_live = true,
                              bool last_command_landed = true);
}
