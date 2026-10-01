"""The compass, computed, against its own face and its own equations.
C1 the eight points sit where the face puts them: + at Α (0 deg), ⇄ at Δ (45), > at Β (90), ⊤ at Λ (135), − at Ω (180),
   ≈ at Π (225), < at Γ (270), ✦ at Ψ (315); the 24 rim letters are 15 degrees apart, clockwise from Α.
C2 the axle's rest point S* solves equation (6): delta - alpha_s S - (3/4) beta_s S^2 = 0.
C3 one turn of the wheel closes one circle: I -> II -> III -> IV -> I, counted at ignition (IV -> I).
C4 G . n <= 0 on the boundary of Omega: at the ceiling nothing moves up, at the floor nothing moves down; inside, anything.
C5 the ledger L = e^2/2 + Phi(S) - Phi(S*) descends along an unforced return to rest."""
import math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omnicompass.compass import Compass, RIM, POINTS, axle, heading, inward, quadrant


def main():
    face = {(0, 1): ("+", "Α", 0), (1, 1): ("⇄", "Δ", 45), (1, 0): (">", "Β", 90), (1, -1): ("⊤", "Λ", 135),
            (0, -1): ("−", "Ω", 180), (-1, -1): ("≈", "Π", 225), (-1, 0): ("<", "Γ", 270), (-1, 1): ("✦", "Ψ", 315)}
    for (e, r), (pt, letter, deg) in face.items():
        h = heading(e, r)
        assert abs(h - deg) < 1e-9, (e, r, h)
        assert POINTS[int(((h + 22.5) % 360) // 45)][0] == pt and RIM[int(((h + 7.5) % 360) // 15)] == letter, (pt, letter)
    assert len(RIM) == 24 and len(set(RIM)) == 24
    for d in (0.05, 0.5, 1.0):
        S = axle(0.12, 0.10, d)
        assert abs(d - 0.12 * S - 0.75 * 0.10 * S * S) < 1e-12
    c = Compass(E_max=1.0); qs = []
    for k in range(0, 2 * 360 + 1, 5):                       # two full turns of a clean oscillation
        t = math.radians(k)
        r = c.read(math.sin(t), axle(0.12, 0.10, 0.5))
        qs.append(r["quadrant"])
    assert c.turns == 2, c.turns
    seq = [q for i, q in enumerate(qs) if i == 0 or q != qs[i - 1]]
    assert all(b == a % 4 + 1 for a, b in zip(seq[1:], seq[2:])), seq
    assert not inward(0.95, +0.1) and inward(0.95, -0.1) and not inward(0.05, -0.1) and inward(0.05, +0.1) and inward(0.5, 0.3)
    c = Compass(E_max=1.0, delta=0.5); s_star = axle(0.12, 0.10, 0.5); steps = []
    for k in range(40):                                       # E decays to rest, S settles onto its axle
        r = c.read(0.9 * math.exp(-0.2 * k), s_star + 0.5 * math.exp(-0.2 * k))
        if r["ledger_step"] is not None:
            steps.append(r["ledger_step"])
    assert all(x <= 1e-9 for x in steps), max(steps)
    print("compass: 8 points and 24 letters where the face puts them; axle solves (6); 2 turns = 2 circles closed;"
          " inward on both boundaries; ledger descends on an unforced return")
    # the composite ledger over all six states descends at every step while the engine's own regulation (equation (2),
    # target basin +1) closes the circle from far outside it, with no outside forcing
    from dataclasses import asdict
    from omnicompass.core import State, Params, macro_step
    from omnicompass.adapter import STACK_PARAMS
    pp = Params(**asdict(STACK_PARAMS)); xx = State(E=0.6, U=0.2, I_U=0.8, S=0.5, B=0.3, B_dot=0.1)
    cc = Compass(E_max=pp.E_max, alpha_s=pp.alpha_s, beta_s=pp.beta_s, delta=pp.delta); tt = 0.0; Ls = []
    for _ in range(60):
        r = cc.read(xx.E, xx.S, x=xx, p=pp); Ls.append(r["ledger"]); assert set(r["ledger_parts"]) == {"V_U", "V_W", "V_E", "V_S", "V_I", "V_B"}
        xx, _ = macro_step(xx, pp, tt, target=1); tt += 0.1
    assert all(b <= a + 1e-9 for a, b in zip(Ls, Ls[1:])) and Ls[-1] < 0.05 * Ls[0], (Ls[0], Ls[-1])
    print(f"composite ledger: {Ls[0]:.1f} -> {Ls[-1]:.2f} over 60 regulated steps, no rise")
    print("PASS test_compass")


if __name__ == "__main__":
    main()
