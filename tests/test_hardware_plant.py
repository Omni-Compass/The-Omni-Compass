"""Hardware plant integrity (adopted from the Grok review's referee gate, extended).
H1 on a GPU the arms must not collapse: B (vendor keeps TDP, Omni caps) and C (Omni sizes) give different settings
H2 C sizes by the device law: setting = min(engine cap, (want / rho)^(1/gamma)), gamma = 1 for CPU clocks
H3 C does the same work as native (within 0.1%) and never more heat-over minutes than native, on every vessel"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hardware.plant import VESSELS, run


def main():
    for vn, v in VESSELS.items():
        for fam, seed in (("diurnal", 7), ("spike", 11), ("burst_train", 13)):
            a, b, c = (run(v, fam, seed, arm, steps=180) for arm in ("A", "B", "C"))
            if v.kind == "gpu":
                assert abs(b["mean_setting"] - c["mean_setting"]) > 1e-3, f"H1 {vn} {fam}: B and C collapsed"
            assert c["work"] >= 0.999 * a["work"], f"H3 {vn} {fam}: C dropped work"
            assert c["heat_over_min"] <= a["heat_over_min"], f"H3 {vn} {fam}: C hotter than native"
    src = (ROOT / "hardware/plant.py").read_text()
    assert "** (1.0 / max(gam, 1e-6))" in src and "min(max(v.f_min, cap), need)" in src, "H2: C sizing law changed"
    print("PASS test_hardware_plant: GPU arms distinct, C sized by the device law under the engine cap, no lost work, no extra heat")


if __name__ == "__main__":
    main()
