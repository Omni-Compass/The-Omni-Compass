// SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
// Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
// Omni-Compass Enterprise License. See LICENSE.
// Governor contract checks: bounds, security, determinism, both modes.
#include "omnicompass/governor.hpp"
#include <cmath>
#include <cstdio>
using namespace omnicompass;
static int fails = 0;
static void expect(bool c, const char* what) { if (!c) { std::printf("FAIL %s\n", what); ++fails; } }
int main() {
  AllocationLaw tp{}; tp.backlog_release = true; tp.power_ceiling = 9.0; tp.power_ceiling_backlog = 9.0; tp.spread_step = 0.0;
  tp.B_cap = 9.0; tp.size_at_full_cap = true; tp.kI = 0.05; tp.kE = 0.40; tp.cap_min = 0.65; tp.down_band = 1; tp.down_dwell = 10;
  tp.down_after_add = 3; tp.kq = 0.30; tp.U_gate = 0.45; tp.push_release = 0.01;
  for (const AllocationLaw& law : {AllocationLaw{}, tp}) {
    Governor g{law}, h{law};
    for (int i = 0; i < 2000; ++i) {
      const double s = 0.5 + 0.5 * std::sin(0.037 * i);
      Observation o{0.4 * s, 0.4 + 0.9 * s, 0.5 + 0.6 * s, 0.3 + 0.7 * s, 0.2 * s, 0.1 * s, 0.0, (i % 97 < 5) ? 1.0 : 0.0, i % 5};
      const int n = 8 + (i % 33);
      Directive d = g.step(o, 0.9, n), e = h.step(o, 0.9, n);
      expect(d.node_delta >= -law.down_max && d.node_delta <= law.up_max, "node delta within bounds");
      expect(d.power_cap >= law.cap_min - 1e-12 && d.power_cap <= 1.0 + 1e-12, "power cap within bounds");
      expect(!(o.security > 0.5) || d.node_delta <= 0, "no capacity addition during security block");
      expect(std::isfinite(d.x.E) && std::isfinite(d.x.U) && std::isfinite(d.x.I_U) && std::isfinite(d.x.S) && std::isfinite(d.x.B), "finite state");
      expect(d.node_delta == e.node_delta && d.power_cap == e.power_cap && d.x.U == e.x.U, "deterministic");
    }
  }
  std::printf(fails ? "SMOKE FAIL (%d)\n" : "SMOKE PASS\n", fails);
  return fails ? 1 : 0;
}
