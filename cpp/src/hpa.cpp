#include "omnicompass/hpa.hpp"
#include <algorithm>
#include <cmath>
namespace omnicompass {
Hpa::Hpa(int replicas, int min_rep, int max_rep, HpaParams p) : replicas_(replicas), min_(min_rep), max_(max_rep), p_(p) {}
int Hpa::step(double metric, double target) {
  const double ratio = metric / std::max(target, 1e-9);
  const int cur = replicas_;
  int rec = cur;
  if (std::abs(ratio - 1.0) > p_.tolerance)
    rec = std::max(min_, std::min(max_, static_cast<int>(std::ceil(static_cast<double>(cur) * ratio))));
  recs_.push_back(rec);
  while (static_cast<int>(recs_.size()) > p_.window_periods) recs_.pop_front();
  const int next = rec > cur ? std::min(rec, cur + std::max(p_.up_pods, cur)) : *std::max_element(recs_.begin(), recs_.end());
  replicas_ = std::max(min_, std::min(max_, next));
  return replicas_;
}
}
