"""A failed decision is recorded and skipped; three failures in a row hand the cluster back to native (kill-switch
restore) and stop the controller, so a dead controller never leaves its settings in place."""
import json, sys, tempfile
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
    c = Stub([False, True, False, True, True, False])
    fails = 0
    for _ in range(6):
        fails = C.safe_step(c, fails)
    assert c.restored == 0 and fails == 0, (c.restored, fails)
    assert sum("error" in r for r in c.log) == 3, c.log
    c = Stub([True, True, True, False])
    fails = 0
    try:
        for _ in range(4):
            fails = C.safe_step(c, fails)
        raise AssertionError("controller kept running after three failures in a row")
    except SystemExit as e:
        assert e.code == 2
    assert c.restored == 1 and any("failsafe" in r for r in c.log), c.log
    print("failsafe ok")


if __name__ == "__main__":
    main()
