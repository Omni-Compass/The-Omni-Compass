#include "omnicompass/closure.hpp"
#include <algorithm>
#include <cmath>
namespace omnicompass {
void ClosureNodes::observe(double r, double dt) {
  if (law_.tone) { hist_.push_back(r); if (static_cast<int>(hist_.size()) > law_.tone_H) hist_.erase(hist_.begin()); }
  if (!has_) { L_ = r; has_ = true; return; }
  const double pred = L_ + v_ * dt, e = r - pred;
  s2_ = 0.95 * s2_ + 0.05 * e * e;
  L_ = pred + law_.a * e;
  v_ = (1.0 - law_.g) * v_ + law_.b * e / dt;
}
double ClosureNodes::fwd_max(int H) const {
  if (!has_) return 0.0;
  double m = L_;
  for (int tau = 0; tau <= H; ++tau) m = std::max(m, L_ + v_ * tau);
  return m;
}
int ClosureNodes::reserve(double c) const {
  if (hist_.empty()) return 0;
  const double mx = *std::max_element(hist_.begin(), hist_.end());
  return static_cast<int>(std::ceil(mx / ((law_.rho_max - law_.delta) * c) - 1e-9));
}
int ClosureNodes::decide(int n, double c, double push, int n_min, int n_max) {
  if (!has_) return n;
  const double peak_add = std::max(fwd_max(law_.H_add), 0.0);
  if (n <= 0 || peak_add / (n * c) - law_.rho_max > -law_.delta) {
    calm_ = 0;
    const int need = static_cast<int>(std::ceil(peak_add / ((law_.rho_max - law_.delta) * c) - 1e-9));
    return std::min(n_max, std::max({n_min, need, n}));
  }
  const double peak_rel = std::max(fwd_max(law_.H_rel), 0.0) + law_.z * std::sqrt(s2_ * std::max(1, law_.H_rel)) * law_.a;
  const double band = law_.delta_rel < 0 ? law_.delta : law_.delta_rel;
  const bool calm = n - 1 >= n_min && peak_rel / ((n - 1) * c) <= law_.rho_max - band && (!law_.turn || v_ <= 0.0) &&
                    push <= law_.push_release;
  calm_ = calm ? calm_ + 1 : 0;
  if (calm && calm_ > law_.dwell) { calm_ = 0; return n - 1; }
  return n;
}
}
