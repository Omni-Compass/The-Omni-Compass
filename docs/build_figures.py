#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Builds docs/figures/*.png from results/. Every plotted value is read from the result files."""
import csv, json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
OUT = ROOT / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
PRE = json.loads((R / "PREREGISTRATION.json").read_text())
SEEDS = PRE["held_out_seeds"]
HO = {sd: json.loads((R / f"heldout_seed_{sd}" / "SUMMARY.json").read_text()) for sd in SEEDS}
NAVY, TEAL, GOLD, GREY, RED, LIGHT = "#1F3A5F", "#2A9D8F", "#E9C46A", "#8D99AE", "#E76F51", "#EDF2F4"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 11})
LABEL = {"native": "Native model", "k8s_ref_50": "K8s ref 0.5", "k8s_ref_60": "K8s ref 0.6", "k8s_ref_70": "K8s ref 0.7",
         "k8s_ref_80": "K8s ref 0.8", "omni_k8s_protect": "Omni + K8s\npower-protect", "omni_k8s_throughput": "Omni + K8s\nthroughput",
         "omni_direct": "Omni replacing\nK8s decisions", "omni_direct_no_dynamics": "no engine\ndynamics",
         "omni_direct_no_shield": "no shield", "omni_pipeline": "pipeline\nsensing"}
COLOR = {"native": GREY, "k8s_ref_50": "#6C757D", "k8s_ref_60": "#6C757D", "k8s_ref_70": "#495057", "k8s_ref_80": "#6C757D",
         "omni_k8s_protect": NAVY, "omni_k8s_throughput": TEAL}


def mean2(arm, m):
    return float(np.mean([HO[sd]["means"][arm][m] for sd in SEEDS]))


def rows(arm, m):
    out = []
    for sd in SEEDS:
        with open(R / f"heldout_seed_{sd}" / "RUNS.csv") as f:
            out += [float(r[m]) for r in csv.DictReader(f) if r["arm"] == arm]
    return np.array(out)


def architecture():
    fig, ax = plt.subplots(figsize=(9, 5.4)); ax.set_xlim(0, 10); ax.set_ylim(0, 6.2); ax.axis("off")
    def box(x, y, w, h, title, sub, fc, tc="white"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=fc, ec="none"))
        ax.text(x + w / 2, y + h - 0.32, title, ha="center", va="top", color=tc, fontsize=11, fontweight="bold")
        ax.text(x + w / 2, y + h - 0.72, sub, ha="center", va="top", color=tc, fontsize=8.5, linespacing=1.35)
    box(0.3, 4.1, 9.4, 1.9, "OMNI-COMPASS", "Engine: six-state dynamics (1)-(8)   |   Governor: sense, assimilate, evolve, allocate\n"
        "Safety shield: invariants I1-I5   |   Modes: power-protect, throughput   |   Kill switch: hand-back", NAVY)
    box(0.3, 2.05, 9.4, 1.6, "KUBERNETES  (execution layer, retained)", "HPA with governor-set target   |   Cluster Autoscaler scale-up   |   scheduler, kubelet, runtime\n"
        "Retired from control: Terraform as live controller, separate power agents, paging path", "#3D5A80")
    box(0.3, 0.2, 9.4, 1.4, "MACHINES", "nodes and replicas   |   power caps   |   cooling and heat   |   network routing", LIGHT, NAVY)
    for x in (2.3, 7.7):
        ax.add_patch(FancyArrowPatch((x, 3.65), (x, 4.1), arrowstyle="-|>", mutation_scale=16, color=GOLD, lw=2.2))
        ax.add_patch(FancyArrowPatch((x + 0.35, 4.1), (x + 0.35, 3.65), arrowstyle="-|>", mutation_scale=16, color=TEAL, lw=2.2))
        ax.add_patch(FancyArrowPatch((x, 1.6), (x, 2.05), arrowstyle="-|>", mutation_scale=16, color=GOLD, lw=2.2))
        ax.add_patch(FancyArrowPatch((x + 0.35, 2.05), (x + 0.35, 1.6), arrowstyle="-|>", mutation_scale=16, color=TEAL, lw=2.2))
    ax.text(5.0, 3.85, "direct sensing (gold)   /   shielded commands (teal)", ha="center", fontsize=8.5, color=NAVY)
    fig.savefig(OUT / "architecture.png", dpi=200, bbox_inches="tight"); plt.close(fig)


def bars(metric, title, ylabel, fname, arms, pct=False):
    fig, ax = plt.subplots(figsize=(8.2, 3.6))
    vals = [mean2(a, metric) * (100 if pct else 1) for a in arms]
    b = ax.bar(range(len(arms)), vals, color=[COLOR.get(a, GREY) for a in arms], width=0.62)
    for r, v in zip(b, vals):
        ax.text(r.get_x() + r.get_width() / 2, v, f"{v:.1f}{'%' if pct else ''}", ha="center", va="bottom", fontsize=8.5)
    ax.set_xticks(range(len(arms))); ax.set_xticklabels([LABEL[a] for a in arms], fontsize=8.5)
    ax.set_ylabel(ylabel); ax.set_title(title, loc="left")
    fig.tight_layout(); fig.savefig(OUT / fname, dpi=200); plt.close(fig)


def violations(arms):
    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    bottom = np.zeros(len(arms))
    for m, c, lab in (("violation_backlog", GOLD, "backlog"), ("violation_power", RED, "power limit"), ("violation_heat", "#9B2226", "heat")):
        v = np.array([100 * mean2(a, m) for a in arms])
        ax.bar(range(len(arms)), v, bottom=bottom, color=c, width=0.62, label=lab); bottom += v
    ax.set_xticks(range(len(arms))); ax.set_xticklabels([LABEL[a] for a in arms], fontsize=8.5)
    ax.set_ylabel("% of intervals (by type, stacked)"); ax.set_title("Violations by type", loc="left"); ax.legend(frameon=False, ncol=3)
    fig.tight_layout(); fig.savefig(OUT / "violations.png", dpi=200); plt.close(fig)


def distribution():
    fig, ax = plt.subplots(figsize=(8.2, 3.6))
    arms = ["k8s_ref_70", "omni_k8s_protect", "omni_k8s_throughput"]
    data = [100 * rows(a, "time_healthy") for a in arms]
    bp = ax.boxplot(data, vert=False, patch_artist=True, widths=0.55, showfliers=True,
                    flierprops=dict(marker=".", markersize=3, alpha=0.4))
    for p, a in zip(bp["boxes"], arms):
        p.set_facecolor(COLOR[a]); p.set_alpha(0.85)
    ax.set_yticks([1, 2, 3]); ax.set_yticklabels([LABEL[a].replace("\n", " ") for a in arms])
    ax.set_xlabel("time healthy per scenario (%)"); ax.set_title("Per-scenario distribution, 1,000 held-out scenarios", loc="left")
    fig.tight_layout(); fig.savefig(OUT / "distribution.png", dpi=200); plt.close(fig)


def sensitivity():
    fig, axes = plt.subplots(1, 3, figsize=(9, 3.2))
    refs = ["k8s_ref_50", "k8s_ref_60", "k8s_ref_70", "k8s_ref_80"]; x = [0.5, 0.6, 0.7, 0.8]
    for ax, (m, t, pct) in zip(axes, (("energy_kwh", "Energy (kWh)", False), ("time_healthy", "Time healthy (%)", True),
                                      ("recovery_minutes", "Recovery (min)", False))):
        k = 100 if pct else 1
        ax.plot(x, [k * mean2(r, m) for r in refs], "o-", color="#495057", label="K8s reference")
        ax.axhline(k * mean2("omni_k8s_protect", m), color=NAVY, lw=2, label="Omni power-protect")
        ax.axhline(k * mean2("omni_k8s_throughput", m), color=TEAL, lw=2, ls="--", label="Omni throughput")
        ax.set_title(t, loc="left"); ax.set_xlabel("HPA target")
    axes[0].legend(frameon=False, fontsize=7.5)
    fig.tight_layout(); fig.savefig(OUT / "sensitivity.png", dpi=200); plt.close(fig)


def main():
    architecture()
    main_arms = ["native", "k8s_ref_70", "omni_k8s_protect", "omni_k8s_throughput"]
    bars("energy_kwh", "Energy per 6-hour run (mean of 1,000 held-out scenarios)", "kWh", "energy.png", main_arms)
    bars("time_healthy", "Time healthy", "% of intervals", "healthy.png", main_arms, pct=True)
    bars("recovery_minutes", "Recovery time after an event", "minutes", "recovery.png", main_arms)
    violations(main_arms)
    distribution()
    sensitivity()
    print("figures:", sorted(p.name for p in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
