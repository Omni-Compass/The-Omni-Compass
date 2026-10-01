#pragma once
// Omni-Compass safety shield: invariants I1-I5 enforced on an action set before execution.
#include <string>
#include <vector>
namespace omnicompass {
struct Action { std::string kind; double target{}; int direction{}; };
struct ShieldLimits { double power_limit{1.00}; int max_node_step{4}; double cap_lo{0.65}, cap_hi{1.00}; };
struct ShieldState { int actual_nodes{}; double power_cap{}; double power_stress{}; double security_block{}; int min_nodes{}, max_nodes{}; };
struct ShieldResult { std::vector<Action> actions; int interventions{}; };
ShieldResult enforce(const std::vector<Action>& actions, const ShieldState& s, const ShieldLimits& lim = {});
std::vector<std::string> violations(const std::vector<Action>& actions, const ShieldState& s, const ShieldLimits& lim = {});
}
