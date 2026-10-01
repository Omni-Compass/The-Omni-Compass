#pragma once
// HorizontalPodAutoscaler replica law (documented behaviour): ratio rule, 10% tolerance, scale-up limited to
// max(4 pods, 100%) per period, scale-down to the highest recommendation within the stabilization window.
#include <deque>
namespace omnicompass {
struct HpaParams { double tolerance{0.1}; int window_periods{20}; int up_pods{4}; };
class Hpa {
 public:
  Hpa(int replicas, int min_rep, int max_rep, HpaParams p = {});
  int step(double metric, double target);
  int replicas() const noexcept { return replicas_; }
 private:
  int replicas_, min_, max_; HpaParams p_; std::deque<int> recs_;
};
}
