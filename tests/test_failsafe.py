# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""No automated fallback (manuscript Section 5.8): a failed decision is recorded and skipped, it writes nothing, and the
controller keeps its cadence however many fail in a row; nothing is handed back or stopped automatically. Only the human
switch (kill file) turns the whole harness OFF, restoring native settings, and removing it turns it back ON."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omni_controller import controller as C


class Stub:
    def __init__(self, plan):
        self.plan, self.a, self.log, self.restored = list(plan), C.parser().parse_args([]), [], 0

    def step(self):
        if self.plan.pop(0):
            raise RuntimeError("kubectl: the server is currently unable to handle the request")

    def audit(self, rec):
        self.log.append(rec)

    def restore(self):
        self.restored += 1


def main():
    c = Stub([True] * 10 + [False])
    fails = 0
    for _ in range(11):
        fails = C.safe_step(c, fails)
    assert c.restored == 0 and fails == 0, (c.restored, fails)          # ten failures in a row: no automatic hand-back
    assert sum("error" in r for r in c.log) == 10 and not any("failsafe" in r for r in c.log), c.log
    print("no automated fallback: 10 failed decisions logged and skipped, nothing restored or stopped; only the human switch turns Omni off")
    print("PASS test_failsafe")


if __name__ == "__main__":
    main()
