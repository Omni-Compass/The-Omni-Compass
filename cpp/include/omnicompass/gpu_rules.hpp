// GPU governor decision rules (C++ twin of the pure functions in omni_controller/gpu_governor.py): the shield's
// limit, the busy gate, the speed lock's step, the baseline lookup and the response-time window. The parts that talk to
// the device (nvidia-smi) stay in the Python controller; every decision it takes goes through these rules.
#pragma once
#include <optional>
#include <string>
#include <vector>
namespace omnicompass {
struct Limit { int want{}; std::string bound; };
Limit shield_limit(double cap, double draw, double start, double min_w, double headroom, double min_share, bool slo_clean);
struct Gate { double u{}; bool gated{}; };
Gate busy_gate(std::optional<double> u_prev, double util, bool gated_prev, double gate, double band);
struct LockStep { int want{}; std::string bound; double line{}, aim{}; };
LockStep lock_decide(double ratio, double cur, double start, double min_w, double since_last, double speed_gain,
                     double lock_margin, double lock_step, double lock_boost, double lock_floor, double lock_hold_s);
struct BaselinePoint { double rate{}, mean{}, p95{}, p99{}; };
BaselinePoint baseline_at(const std::vector<BaselinePoint>& bins, double rate);
struct Row { double t{}, ms{}; bool ok{}; };
struct WindowStats { double mean{}, p95{}, p99{}, rate{}; int n{}; };
std::optional<WindowStats> window_stats(const std::vector<Row>& rows, double window_s);
}
