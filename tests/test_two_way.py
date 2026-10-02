# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Two-way nervous system (manuscript Appendix J: the nervous system owns sensing integrity, delay and dropout handling,
and feedback interpretation).
W1 afferent integrity: a blind sense (stale > 0) never grants any organ contraction and never admits held batch work,
   over random engine states; capacity expansion is untouched (the safe direction), and pausing batch (its protective
   contraction) stays allowed
W2 the latency sense is judged against the wall clock: a frozen probe file is blind even if its last window was clean
   (a hung probe must never be read as the present); a window with no successful request is blind; a fresh clean window is live
W3 failed requests in a live window become latency pressure (a failure is never read as silence)
W4 efferent feedback: the node gate refuses a new release while a sense is blind or the last node command did not land"""
import csv, os, random, sys, tempfile, time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omnicompass.nervous_system import NervousInputs, authority, node_release_gate
from omni_controller.muscles import latency_sense, Muscles


def probe(rows):
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
    w = csv.writer(f); w.writerow(["elapsed_seconds", "latency_ms", "ok"]); w.writerows(rows); f.close()
    return f.name


def main():
    rng = random.Random(11); n = 0
    for _ in range(100_000):                                                                            # W1
        i = NervousInputs(E=rng.random(), U=rng.uniform(0.5, 1.0), I_U=rng.uniform(-0.2, 0.3), S=rng.random() * 0.5,
                          push=rng.uniform(0, 0.3), stale=rng.choice([0.0, 0.25, 0.5, 1.0]), slo_clean=rng.random() < 0.8)
        a = authority(i)
        if i.stale > 0:
            assert not any(o.get("contract") for o in a["organs"].values() if not o.get("protective_contract")), a
            assert not a["organs"]["batch"]["admit"], "held work admitted on a blind sense"; n += 1
            assert a["organs"]["nodes"]["expand"] and a["organs"]["pods"]["expand"]
    live = probe([(t, 200 + t % 7, 1) for t in range(0, 120, 1)])                                        # W2
    assert not latency_sense(live, 60)["blind"]
    old = time.time() - 600; os.utime(live, (old, old))
    assert latency_sense(live, 60)["blind"], "frozen probe file read as live"
    dead = probe([(t, 10000, 0) for t in range(0, 120, 1)])
    assert latency_sense(dead, 60)["blind"]
    mixed = probe([(t, 300, 1 if t % 4 else 0) for t in range(0, 120, 1)])                             # W3
    m = Muscles(None, SimpleNamespace(latency_file=mixed, slo_ms=500, latency_window_s=60, thermal_model=False,
                                      gpu_temp_cmd="", security_configmap=""), lambda r: None)
    o = m.sense(0.1)
    assert o["latency_blind"] == 0.0 and o["latency_pressure"] >= 0.2, o
    YES = {"organs": {"nodes": {"contract": True}}}                                                     # W4
    assert node_release_gate(6, 4000, 1700, 0, False, False, 0.8, YES)["ok"]
    r = node_release_gate(6, 4000, 1700, 0, False, False, 0.8, YES, senses_live=False)
    assert not r["ok"] and "blind" in r["reason"]
    r = node_release_gate(6, 4000, 1700, 0, False, False, 0.8, YES, last_command_landed=False)
    assert not r["ok"] and "did not land" in r["reason"]
    print(f"blind sense never granted contraction in {n:,} blind states; frozen probe detected; failures read as pressure; "
          "release refused while blind or after an order that did not land")
    print("PASS test_two_way")


if __name__ == "__main__":
    main()
