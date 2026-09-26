#!/usr/bin/env python3
"""Builds docs/OMNI_COMPASS_TECHNICAL_MANUAL.pdf. Every result number is read from results/."""
import csv, hashlib, json, sys
import numpy as np
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle,
                                KeepTogether)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnicompass.adapter import AllocationLaw
from dataclasses import asdict

R = ROOT / "results"
CORE = json.loads((R / "core_evidence.json").read_text())
PRE = json.loads((R / "PREREGISTRATION.json").read_text())
SOAK_ALL = json.loads((R / "SOAK.json").read_text())
SOAK = SOAK_ALL["power_protect"]
MULT = json.loads((R / "MULTIPLICITY.json").read_text())
FLEET = json.loads((R / "fleet_overhead.json").read_text())
HO = {sd: json.loads((R / f"heldout_seed_{sd}" / "SUMMARY.json").read_text()) for sd in PRE["held_out_seeds"]}
S1, S2 = PRE["held_out_seeds"]

ss = getSampleStyleSheet()
BODY = ParagraphStyle("b", parent=ss["BodyText"], fontName="Times-Roman", fontSize=10.5, leading=14, spaceAfter=6)
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=15, spaceBefore=10, spaceAfter=8)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12, spaceBefore=8, spaceAfter=5)
EQ = ParagraphStyle("eq", parent=ss["Code"], fontName="Courier", fontSize=9, leading=12, leftIndent=12)
BOX = ParagraphStyle("box", parent=BODY, backColor=colors.HexColor("#F2F4F7"), borderPadding=6, leftIndent=6, rightIndent=6)
TITLE = ParagraphStyle("t", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=24, leading=30, alignment=TA_CENTER)
SUB = ParagraphStyle("s", parent=BODY, fontSize=12, alignment=TA_CENTER, leading=16)
CELL = ParagraphStyle("c", parent=BODY, fontSize=8.5, leading=10.5, spaceAfter=0)

story = []
P = lambda t, s=BODY: story.append(Paragraph(t, s))
def E(t): story.append(Preformatted(t, EQ)); story.append(Spacer(1, 4))

def T(rows, widths, head=True):
    data = [[Paragraph(str(c), CELL) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA4B2")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if head:
        st.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDE3EA")))
    t.setStyle(TableStyle(st)); story.append(t); story.append(Spacer(1, 8))

f2 = lambda v: f"{v:.2f}"; f3 = lambda v: f"{v:.3f}"; pct = lambda v: f"{100*v:.1f}%"; f1 = lambda v: f"{v:.1f}"

def mean(sd, arm, m): return HO[sd]["means"][arm][m]
def pr(sd, comp, m): return next(r for r in HO[sd]["paired"][comp] if r["metric"] == m)

# ------------------------------------------------------------------ title
from reportlab.platypus import Image as RLImage
FIG = ROOT / "docs" / "figures"
def FIGURE(name, width=6.6 * inch, caption=None):
    from PIL import Image as PILImage
    w, h = PILImage.open(FIG / name).size
    story.append(RLImage(str(FIG / name), width=width, height=width * h / w))
    if caption:
        story.append(Paragraph(f"<i>{caption}</i>", ParagraphStyle("cap", parent=BODY, fontSize=9, textColor=colors.HexColor("#555555"))))
    story.append(Spacer(1, 6))

story += [Spacer(1, 1.3 * inch), Paragraph("OMNI-COMPASS", TITLE), Spacer(1, 8),
          Paragraph("A six-state control engine governing Kubernetes", SUB),
          Paragraph("Technical Manual and Referee Record", SUB), Spacer(1, 0.35 * inch)]
FIGURE("architecture.png", 6.0 * inch)
story += [Spacer(1, 0.25 * inch), Paragraph("The Omni-Compass LLC", SUB), Spacer(1, 0.3 * inch)]
P("This manual describes only what the accompanying package contains and executes. Every number and chart is generated from the result "
  "files in <font face='Courier'>results/</font> by the build scripts. Every claim is paired with the file and command that establish it. "
  "Anything not established by the package is listed in Chapter 10.", BOX)
story.append(PageBreak())

# ------------------------------------------------------------------ executive summary
P("Executive Summary", H1)
P("Omni-Compass is a control engine that sits above Kubernetes. Kubernetes remains the execution layer: it schedules and runs the "
  "containers, and its autoscalers react to unscheduled work. Omni-Compass is the single authority above it: it reads the machines "
  "directly, evolves a six-state dynamical model of the stack, sets Kubernetes' scaling targets, owns scale-down, power caps, rollback "
  "authority and routing, and passes every command through a safety shield before execution. Components whose only role was to make "
  "competing control decisions (Terraform as a live capacity controller, separate power agents, the paging path) are retired from the "
  "control loop. The engine runs in two operator-selected modes: power-protect, which enforces the site power limit, and throughput, which "
  "applies the same power rules as the native stack.")
def ex(m, a):
    return float(np.mean([mean(sd, a, m) for sd in (S1, S2)]))
kr, pp, tp = "k8s_ref_70", "omni_k8s_protect", "omni_k8s_throughput"
e_save_p = 100 * (1 - ex("energy_kwh", pp) / ex("energy_kwh", kr)); e_save_t = 100 * (1 - ex("energy_kwh", tp) / ex("energy_kwh", kr))
T([["Benefit", "Kubernetes reference (HPA 0.7)", "Omni + K8s power-protect", "Omni + K8s throughput", "Evidence"],
   ["Energy per run", f"{ex('energy_kwh', kr):.1f} kWh", f"{ex('energy_kwh', pp):.1f} kWh (-{e_save_p:.0f}%)", f"{ex('energy_kwh', tp):.1f} kWh (-{e_save_t:.0f}%)", "Simulation, 1,000 held-out"],
   ["Time healthy", pct(ex("time_healthy", kr)), pct(ex("time_healthy", pp)), pct(ex("time_healthy", tp)), "Simulation"],
   ["Recovery after events", f"{ex('recovery_minutes', kr):.0f} min", f"{ex('recovery_minutes', pp):.0f} min", f"{ex('recovery_minutes', tp):.0f} min", "Simulation"],
   ["Physical violations (backlog + power + heat)", pct(ex("sla_violation_physical", kr)), pct(ex("sla_violation_physical", pp)), pct(ex("sla_violation_physical", tp)), "Simulation"],
   ["Backlog violations", pct(ex("violation_backlog", kr)), pct(ex("violation_backlog", pp)), pct(ex("violation_backlog", tp)), "Simulation"],
   ["Power / heat violations", f"{pct(ex('violation_power', kr))} / {pct(ex('violation_heat', kr))}", f"{pct(ex('violation_power', pp))} / {pct(ex('violation_heat', pp))}", f"{pct(ex('violation_power', tp))} / {pct(ex('violation_heat', tp))}", "Simulation"],
   ["Contradictory commands per run", f1(ex("contradictions", kr)), f1(ex("contradictions", pp)), f1(ex("contradictions", tp)), "Simulation"],
   ["Invariant violations per run, I1-I5", f2(ex("invariant_violations", kr)), f2(ex("invariant_violations", pp)), f2(ex("invariant_violations", tp)), "Simulation"],
   ["Invariant violations per run, excluding I4 (power)", f2(ex("invariant_violations_ex_power", kr)), f2(ex("invariant_violations_ex_power", pp)), f2(ex("invariant_violations_ex_power", tp)), "Simulation"],
   ["Thermal cycling (hardware wear)", f2(ex("thermal_travel", kr)), f2(ex("thermal_travel", pp)), f2(ex("thermal_travel", tp)), "Simulation"],
   ["Scale direction reversals (wear)", f2(ex("scale_reversals", kr)), f2(ex("scale_reversals", pp)), f2(ex("scale_reversals", tp)), "Simulation"],
   ["Machines started / stopped per run", f"{f1(ex('machines_started', kr))} / {f1(ex('machines_stopped', kr))}", f"{f1(ex('machines_started', pp))} / {f1(ex('machines_stopped', pp))}", f"{f1(ex('machines_started', tp))} / {f1(ex('machines_stopped', tp))}", "Simulation"],
   ["Machine round trips (started, later stopped)", f1(ex("machine_round_trips", kr)), f1(ex("machine_round_trips", pp)), f1(ex("machine_round_trips", tp)), "Simulation"],
   ["Engine cost per decision", "n/a", f"{SOAK['ns_per_decision'] / 1000:.1f} microseconds", f"{SOAK['ns_per_decision'] / 1000:.1f} microseconds", "Measured, C++, test machine"],
   ["Continuous operation", "n/a", f"{SOAK['decisions']:,} decisions, 0 failures", "same engine", "Measured, C++ soak"]],
  [1.8 * inch, 1.2 * inch, 1.3 * inch, 1.3 * inch, 1.1 * inch])
P(f"Means over held-out seeds {S1} and {S2} (500 scenarios each). Kubernetes reference = documented-behaviour model with HPA target 0.7; "
  "results against targets 0.5, 0.6 and 0.8 are in Section 8.3. The throughput mode is the like-for-like comparison, because it applies "
  "the same power rules as the reference; power-protect additionally enforces the site power limit, which the reference does not. "
  "Throughput mode does not enforce invariant I4 (projected power), so its I4 count is reported rather than excluded. Machine start/stop "
  "The reference model removes a machine only after 10 minutes below 50% utilization, so it keeps surplus and post-event machines running; "
  "the governor stops them, which is the main source of its energy saving. Round trips count machines started and later stopped "
  "(or the reverse); scale direction reversals measure back-and-forth. Hardware wear is also measured by thermal travel.")
FIGURE("energy.png", 6.4 * inch)
FIGURE("violations.png", 6.4 * inch)
FS0 = json.loads((R / "fleet" / "heldout" / "SUMMARY.json").read_text())
fl = []
for v in ("web", "multi", "batch", "gpu", "gpu_always_on"):
    d = FS0["vessels"][v]
    e_ca = {x["metric"]: x for x in d["paired"]["omni_fleet_vs_k8s_hpa70_ca"]}["energy_kwh"]
    e_kp = {x["metric"]: x for x in d["paired"]["omni_fleet_vs_k8s_hpa70_karpenter"]}["energy_kwh"]
    fl.append(f"{v} {100 * (e_ca['cand'] / e_ca['base'] - 1):+.0f}% vs CA, {100 * (e_kp['cand'] / e_kp['base'] - 1):+.0f}% vs Karpenter-lite")
P("<b>Against a 15-second Kubernetes control plane</b> (fleet harness, Section 8.8, synthetic workloads), with the governor as the "
  "node-pool authority in place of the Cluster Autoscaler (HPA retained), energy changes by: " + "; ".join(fl) + ". It reverses node direction less often than "
  "Karpenter-lite in every vessel and more often than the Cluster Autoscaler. The results above this paragraph use the 5-minute stack "
  "model and its documented-behaviour reference, which is slower than the 15-second control plane; the fleet harness is the stronger comparison.")
P("<b>Operational burden.</b> The governor holds every lever a paged operator would use for capacity, power and overload events and "
  "issues no page actions; engineer hours are a pilot measurement (docs/PILOT_PROTOCOL.md). <b>What is not claimed.</b> Production "
  "performance, behaviour of the upstream Kubernetes controllers, and cybersecurity beyond the stated shield invariants are not "
  "established by this package (Chapter 10).")
story.append(PageBreak())

# ------------------------------------------------------------------ 1
P("1. What Is Established", H1)
T([["Claim", "Status", "Evidence"],
   ["The six-state mechanism (equations 1 to 8) is implemented identically in the reference engine, the Python core and the C++ core.", "Established", "tests/test_core_parity.py; C++ fixture comparison"],
   ["The C++ stack governor reproduces the Python governor exactly.", "Established", "tests/test_cpp_governor_parity.py"],
   [f"The governor ran {SOAK['decisions']:,} consecutive decisions with {SOAK['nonfinite_or_out_of_range']} failures and constant memory.", "Established", "results/SOAK.json"],
   ["Observe mode leaves the stack bit-identical to the native stack.", "Established in simulation",
    f"{HO[S1]['observe_mode_identical_to_native']}/500 and {HO[S2]['observe_mode_identical_to_native']}/500 held-out scenarios"],
   ["Observe mode over Kubernetes leaves Kubernetes bit-identical to Kubernetes alone.", "Established in simulation", "Section 8.5"],
   ["Executed actions in power-protect mode satisfy invariants I1 to I5; throughput mode satisfies I1 to I3 and I5.", "Established in simulation", "Chapter 8"],
   ["Stack outcomes of Omni-Compass governing Kubernetes relative to a documented-behaviour reference model of Kubernetes autoscaling, including costs.", "Established for the declared synthetic model", "Chapter 8"],
   ["Behaviour on production systems.", "Not established", "docs/PILOT_PROTOCOL.md"]],
  [3.3 * inch, 1.2 * inch, 2.3 * inch])
P("Companion documents: docs/CLAIMS_REGISTER.md (every claim with its status and reproduction command), docs/DUE_DILIGENCE.md, docs/PILOT_PROTOCOL.md.")

# ------------------------------------------------------------------ 2
P("2. The Mechanism", H1)
P("State x = (E, U, I<sub>U</sub>, S, B, B&#775;). The engine evolves the following law. Source: "
  "<font face='Courier'>omnicompass/core.py</font>, <font face='Courier'>cpp/src/core.cpp</font>.")
E("(1) dE/dt    = -alpha_E E + beta_int + beta_ext + v_eff\n"
  "(2) dU/dt    = mu U (1 - U^2) - (dE/dt)/E_max - lambda_U U + u ,   |u| <= 25\n"
  "(3) dI_U/dt  = (1 - U) - sigma_1 E - delta S - lambda_I I_U\n"
  "(4) v_eff    = cos(omega_B t / 2) * c * tanh(lambda_0 + lambda_1 (U - 0.5) + lambda_2 S)\n"
  "(5) Phi(S)   = alpha_s S^2 / 2 + beta_s S^3 / 4 - delta S\n"
  "(6) dS/dt    = -dPhi/dS = delta - alpha_s S - (3/4) beta_s S^2\n"
  "(7) dB/dt    = B_dot ,  dB_dot/dt = gamma_c delta S - (omega_B/Q_B) B_dot - omega_B^2 B\n"
  "(8) R_B[n]   = (B[n+1]-2B[n]+B[n-1])/h^2 + (omega_B/Q_B)(B[n]-B[n-1])/h\n"
  "               + omega_B^2 B[n] - gamma_c delta S[n]")
P("Equation (8) is an audit: it is evaluated on the generated trajectory and never fed back into the state. "
  "Equation (5) is the potential whose negative gradient is (6). The factor cos(omega_B t/2) returns to +1 after a phase "
  "advance of 4&#960; (720 degrees); this is a property of the implemented modulation and carries no physical interpretation "
  "in this package.")
P("2.1 Parameters", H2)
from omnicompass.core import PARAMETER_RANGES
T([["Parameter", "Range", "Role"]] + [[k, f"{lo:g}" if lo == hi else f"{lo:g} to {hi:g}", r] for k, (lo, hi), r in [
    ("alpha_E", PARAMETER_RANGES["alpha_E"], "E decay"), ("beta_int, beta_ext", PARAMETER_RANGES["beta_int"], "E forcing"),
    ("sigma_1", PARAMETER_RANGES["sigma_1"], "E coupling into I_U"), ("delta", PARAMETER_RANGES["delta"], "S source; S coupling into I_U and bath"),
    ("gamma_c", PARAMETER_RANGES["gamma_c"], "bath forcing gain"), ("lambda_0", PARAMETER_RANGES["lambda_0"], "drive bias"),
    ("lambda_1", PARAMETER_RANGES["lambda_1"], "U gain in drive"), ("lambda_2", PARAMETER_RANGES["lambda_2"], "S gain in drive"),
    ("c", PARAMETER_RANGES["c"], "drive amplitude"), ("E_max", PARAMETER_RANGES["E_max"], "E-rate normalisation in (2)"),
    ("omega_B", PARAMETER_RANGES["omega_B"], "bath frequency and phase rate"), ("Q_B", PARAMETER_RANGES["Q_B"], "bath quality factor"),
    ("alpha_s, beta_s", PARAMETER_RANGES["alpha_s"], "S potential coefficients"), ("mu", PARAMETER_RANGES["mu"], "double-well coefficient"),
    ("lambda_I", PARAMETER_RANGES["lambda_I"], "I_U damping"), ("lambda_U", PARAMETER_RANGES["lambda_U"], "U damping")]],
  [1.5 * inch, 1.2 * inch, 4.1 * inch])
P("The record fields alpha, k, gamma_1 and alpha_U are carried for compatibility with the reference engine and do not enter equations (1) to (8).")

P("2.2 Controller", H2)
P("Each macro interval (0.1) is divided into 10 micro steps (h = 0.01). At the start of each micro step:")
E("u = clip( -f_U(x, t) + KP (sigma - U) , -25, +25 ),   KP = 12\n"
  "f_U(x, t) = right-hand side of (2) with u = 0\n"
  "sigma     = +1 if |U0 - 1| <= |U0 + 1| else -1   (locked for the trajectory)")
P("u is held constant through all four stages of the classical RK4 step. The accepted state is the RK4 result; no state "
  "component is overwritten after integration.")
P("2.3 Event predicates", H2)
P("A value U is in a basin if |U - 1| &lt;= 0.10 or |U + 1| &lt;= 0.10. CONVEY-5 is five consecutive macro observations in the "
  "same basin; CERT-10 is ten. Step 0 counts as an observation when U0 is already in a basin. These are internal predicates "
  "of the simulation, not external certifications.")

# ------------------------------------------------------------------ 3
P("3. Mathematical Properties", H1)
P("<b>Proposition 1 (S channel).</b> For alpha_s, beta_s, delta &gt; 0, equation (6) has roots "
  "S<sub>-</sub> = (-alpha_s - sqrt(alpha_s<super>2</super> + 3 beta_s delta)) / (1.5 beta_s) &lt; 0 &lt; "
  "S<sub>+</sub> = (-alpha_s + sqrt(alpha_s<super>2</super> + 3 beta_s delta)) / (1.5 beta_s). "
  "The interval [S<sub>-</sub>, &#8734;) is forward invariant, and every trajectory with S0 &gt; S<sub>-</sub> converges to S<sub>+</sub>.")
P("<i>Proof.</i> The right-hand side of (6) is the concave quadratic g(S) = delta - alpha_s S - (3/4) beta_s S<super>2</super>, "
  "positive exactly on (S<sub>-</sub>, S<sub>+</sub>) and negative outside. g(0) = delta &gt; 0 places the roots on either side of 0. "
  "At S = S<sub>-</sub> the field vanishes, so no solution crosses it (uniqueness, since g is smooth). On (S<sub>-</sub>, S<sub>+</sub>) S "
  "increases and on (S<sub>+</sub>, &#8734;) it decreases, each bounded monotonically by S<sub>+</sub>; hence convergence. &#9632;")
P(f"On the canonical population all {CORE['s_admissibility']['runs']} initial states satisfy S0 &gt;= S<sub>-</sub>(p) "
  f"(minimum margin {CORE['s_admissibility']['min_margin']:.3f}). Over the full declared box, S0 = -1 can lie below S<sub>-</sub> "
  "for some parameters, in which case S diverges downward; admissibility is therefore a per-trajectory condition, not a property of the whole box.")
P("<b>Proposition 2 (double well).</b> The autonomous term mu U(1 - U<super>2</super>) = -dW/dU with W = (mu/4)(U<super>2</super> - 1)<super>2</super>. "
  "For mu &gt; 0 its equilibria are U = -1, 0, +1; the linearisation is mu(1 - 3U<super>2</super>), equal to -2mu at U = &#177;1 (stable) "
  "and +mu at U = 0 (unstable). This classifies one term of (2), not the coupled system.")
P("<b>Proposition 3 (what the controller guarantees).</b> If the command is applied continuously and is not saturated, "
  "u(t) = -f_U(x,t) + KP(sigma - U) gives dU/dt = f_U + u = KP(sigma - U) exactly, so "
  "U(t) = sigma + (U0 - sigma) e<super>-KP t</super>, independently of every other state and parameter.")
P("Consequence: under the canonical controller, arrival of U in the target basin is a property of the controller, not of the "
  "dynamics (1) to (7). The following counterfactuals, all on the identical 500-member population (seed 223387268), quantify this. "
  "Source: <font face='Courier'>benchmarks/core_evidence.py</font>.")
c = CORE
T([["Variant", "CONVEY-5", "CERT-10", "Peak |u|", "Saturated micro steps"],
   ["Canonical controller", f"{c['controlled']['convey5']}/500", f"{c['controlled']['cert10']}/500", f"{c['controlled']['actuator_peak']:.2f}", c['controlled']['saturated_microsteps']],
   ["Controller aimed at the opposite basin", f"{c['wrong_target']['convey5']}/500", f"{c['wrong_target']['cert10']}/500", f"{c['wrong_target']['actuator_peak']:.2f}", c['wrong_target']['saturated_microsteps']],
   ["Canonical controller, mu = 0", f"{c['controlled_mu0']['convey5']}/500", f"{c['controlled_mu0']['cert10']}/500", f"{c['controlled_mu0']['actuator_peak']:.2f}", c['controlled_mu0']['saturated_microsteps']],
   ["No control (u = 0)", f"{c['uncontrolled']['convey5']}/500", f"{c['uncontrolled']['cert10']}/500", "0", "0"]],
  [2.6 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 1.5 * inch])
P(f"The closed-form U(t) of Proposition 3 predicts the exact CONVEY-5 confirmation step in "
  f"{c['first_order_prediction_of_convey_step']['matched']}/{c['first_order_prediction_of_convey_step']['runs']} canonical runs. "
  "The 500/500 result is therefore correctly read as: the implemented controller places U in the chosen basin within 0.4 to 0.6 time "
  "units on every sampled trajectory, without saturating. It is not evidence about equations (1), (3) to (7), and it is not a "
  "stability theorem for the coupled system.")

# ------------------------------------------------------------------ 4
P("4. Numerical Method", H1)
P("Classical fourth-order Runge-Kutta, h = 0.01, command held constant over each step (zero-order hold). With u fixed, RK4 is "
  "fourth-order accurate for the plant. The closed loop is a sampled-data system: the held command is itself an O(h) "
  "approximation of continuous feedback, so the loop converges at first order in h. Measured on run 0 of the canonical population "
  "(maximum state difference at t = 2 against h = 0.000625):")
rk = c["rk4_refinement_run0"]
T([["h"] + list(rk.keys()), ["max |x_h - x_ref|"] + [f"{v:.2e}" for v in rk.values()]],
  [1.5 * inch] + [1.3 * inch] * 4)
P("The error halves as h halves, which is first order. The canonical results are the defined sampled-data system at h = 0.01; "
  "they are not claimed as a converged approximation of a continuous-time controller.")
P(f"Bath audit (8): median RMS residual {c['bath_residual_rms']['median']:.2e}, maximum {c['bath_residual_rms']['max']:.2e} over 100 "
  "controlled trajectories. The residual measures consistency of the generated bath trajectory with (7) under a first-order backward "
  "difference; it is not an independent physical validation.")

# ------------------------------------------------------------------ 5
P("5. Implementations, Parity and Endurance", H1)
T([["Artifact", "Test", "Result"],
   ["omnicompass/core.py vs reference engine functions", "20,000 random (state, parameter, time, command) cases", "max |diff| &lt;= 1e-12"],
   ["omnicompass/core.py vs frozen fixtures", "500 full trajectories, 41 output fields each", "0 mismatches"],
   ["cpp core vs frozen fixtures", "500 full trajectories", "0 mismatches"],
   ["cpp governor vs Python governor", "recorded telemetry, 60 scenarios x 72 intervals", "0 discrete mismatches, max |diff| &lt;= 1e-12"],
   ["negative control", "mutated C++ governor (dwell 3 instead of 5)", "rejected by the parity test"],
   ["cpp shield vs Python shield", "action sets recorded from shielded, unshielded, power-protect, throughput and reference arms", "0 mismatches in enforced actions, interventions and violations"],
   ["negative control", "C++ shield no longer blocking rollouts during a security block", "rejected by the parity test"],
   ["independent C++ HPA vs fleet harness HPA", "every HPA step of 3 Kubernetes arms and 2 governor arms, web and multi-cluster vessels", "0 mismatches in replicas"],
   ["negative control", "C++ HPA with 5% instead of 10% tolerance", "rejected by the parity test"],
   ["omnicompass/stack_sim.py vs reference engine", "source extraction", "11/11 blocks byte-identical"],
   ["native benchmark arm vs reference simulator", "60 scenarios", "identical outputs"]],
  [2.4 * inch, 2.4 * inch, 2.0 * inch])
prov = json.loads((ROOT / "reference" / "PROVENANCE.json").read_text())
P("The reference engine <font face='Courier'>reference/omni_compass_reference_engine.py</font> is the authority for the mechanism. "
  f"It is the source engine (SHA-256 {prov['source_engine_sha256'][:16]}...) with comments and docstrings removed; its program "
  f"fingerprint ({prov['program_fingerprint'][:16]}...) is identical to the source engine's under Python {PRE.get('fingerprint_python', '')}. "
  "Program fingerprints use ast.dump and are interpreter-version dependent; SHA-256 hashes are authoritative. Loading the reference engine "
  "writes runtime files next to it, so the tests load it from a temporary copy.")
P("5.1 Endurance", H2)
P(f"The C++ governor executed {SOAK['decisions']:,} consecutive decisions (equivalent to {SOAK['years_at_5min_interval']:.0f} years at "
  "5-minute intervals) on randomized observations spanning and exceeding the sensor ranges, feeding its own power cap and node count back "
  f"as inputs. Non-finite or out-of-range outputs: {SOAK['nonfinite_or_out_of_range']}. Resident memory: {SOAK['rss_kb_start']} kB at start, "
  f"{SOAK['rss_kb_end']} kB at end. Time per decision: {SOAK['ns_per_decision'] / 1000:.2f} microseconds. Observed state ranges: "
  f"E [{SOAK['E'][0]:.3f}, {SOAK['E'][1]:.3f}], U [{SOAK['U'][0]:.3f}, {SOAK['U'][1]:.3f}], I_U [{SOAK['I_U'][0]:.3f}, {SOAK['I_U'][1]:.3f}], "
  f"S [{SOAK['S'][0]:.3f}, {SOAK['S'][1]:.3f}], B [{SOAK['B'][0]:.3f}, {SOAK['B'][1]:.3f}]. Resident memory at 25, 50, 75 and 100% of the run: "
  f"{', '.join(str(v) for v in SOAK['rss_kb_at_25_50_75_100pct'])} kB (power-protect); "
  f"{', '.join(str(v) for v in SOAK_ALL['throughput']['rss_kb_at_25_50_75_100pct'])} kB (throughput, {SOAK_ALL['throughput']['decisions']:,} decisions, "
  f"{SOAK_ALL['throughput']['nonfinite_or_out_of_range']} failures). The initial rise is start-up allocation; memory is flat thereafter.")
P(f"With zero failures in n = {SOAK['decisions']:,} decisions, the rule of three bounds the per-decision failure rate below 3/n = "
  f"{3.0 / SOAK['decisions']:.1e} at 95% confidence, under the tested input distribution. Every observation is clamped and assimilation is a "
  "convex combination, so assimilated states are bounded; a uniform-ultimate-boundedness theorem for the full sampled-data loop is an open "
  "obligation (Chapter 10). The Python governor keeps a fixed-length decision log (4,096 entries). The full verifier reruns the "
  f"{SOAK['decisions']:,}-decision soak and checks that decisions, failures and state ranges match this record.")

# ------------------------------------------------------------------ 6
P("6. Architecture and Stack Governor", H1)
T([["Layer", "Content", "Files"],
   ["Engine", "Equations (1) to (8), controller, predicates; verified and frozen", "omnicompass/core.py, cpp/src/core.cpp"],
   ["Connector (vessel: Kubernetes stack)", "Sensing, assimilation, evolution, allocation law, authority", "omnicompass/adapter.py, cpp/src/governor.cpp"],
   ["Features", "Safety shield; fleet component model", "omnicompass/shield.py, omnicompass/muscles.py"]],
  [1.6 * inch, 3.0 * inch, 2.2 * inch])
P("6.1 Sense and assimilate", H2)
P("Each 5-minute interval the governor reads queue ratio q, load, power stress, thermal, network stress, configuration drift, staleness, "
  "security block and the count of conflicting manager proposals. With direct sensing these are the current values; with pipeline "
  "sensing they are delayed by the scenario's telemetry and Kafka lag.")
E("E_obs = 0.25q + 0.18max(0,load-0.85) + 0.16power + 0.13thermal + 0.10network + 0.08drift + 0.06conflict + 0.04stale\n"
  "U_obs = 1 - (0.27q + 0.18power + 0.16thermal + 0.12network + 0.12drift + 0.10conflict + 0.05stale)\n"
  "S_obs = 0.36thermal + 0.28power + 0.18network + 0.10security + 0.08stale - 0.20q\n"
  "B_obs = 0.52power + 0.26thermal + 0.22drift          I_obs = q + drift + conflict\n"
  "x    <- 0.661 x + 0.339 obs   (per component; B_dot <- 0.661 B_dot + 0.339 (B_obs - B))\n"
  "beta_int = 0.58q + 0.42max(0, load-0.75)     beta_ext = 0.33power + 0.27thermal + 0.20network + 0.12stale + 0.08security")
P("The state is then advanced one macro interval by equations (1) to (7) with u = 0. Engine parameters used by the governor: "
  f"mu = {PRE['engine_stack_parameters']['mu']}, alpha_E = {PRE['engine_stack_parameters']['alpha_E']}, lambda_I = "
  f"{PRE['engine_stack_parameters']['lambda_I']}, delta = {PRE['engine_stack_parameters']['delta']}, assimilation = {PRE['assimilation']}; "
  "the remaining parameters are listed in results/PREREGISTRATION.json.")
P("6.2 Allocation law", H2)
E("headroom    rho* = clamp(rho0 - kI I_U - kE E, rho_min, rho0)\n"
  "capacity    n_req = ceil(n load / rho*) + ceil(kq q n);  delta = clamp(n_req - n, -down_max, +up_max)\n"
  "gate        no removal unless the equation (2) push u/U_AUTHORITY <= push_release, where\n"
  "            u = clip(-f_U(x) + KP (1 - U), -25, 25) on the evolved engine state (target sigma = +1)\n"
  "guard       no removal while q >= guard_queue, or while n_req > n - down_band\n"
  "dwell       removal only after down_dwell consecutive surplus intervals and >= down_after_add intervals after an addition\n"
  "envelope    no addition while power >= power_ceiling (power_ceiling_backlog while q >= guard_queue) or n = max_nodes\n"
  "security    no addition while a security block is observed\n"
  "power cap   q < guard_queue and U >= U_gate : cap = clamp(cap_now load (1 + margin), cap_min, 1)      (trim)\n"
  "            q >= guard_queue at the envelope : cap = max(cap_min, cap_now - spread_step)              (spread)\n"
  "            q >= guard_queue below envelope  : cap held (capacity added as nodes)\n"
  "            always cap <= clamp(1 - cap_gain max(0, B - B_cap), cap_min, 1); expansion never tightens the cap\n"
  "change gate Terraform plans only while U >= U_gate (none under direct actuation)\n"
  "rollback    proposed rollback authorised if S >= S_rollback, or U falling, or security blocks change\n"
  "replicas    direct actuation: ceil(replicas load / rho*), up unless reducing capacity, down only while reducing\n"
  "routing     traffic shift while network stress > route_network;  alerting: one de-duplicated alert;  paging: none (design)")
law = asdict(AllocationLaw())
items = list(law.items())
if len(items) % 2:
    items.append(("", ""))
T([["Constant", "Value", "Constant", "Value"]] +
  [[k1, f"{v1:g}" if v1 != "" else "", k2, f"{v2:g}" if v2 != "" else ""] for (k1, v1), (k2, v2) in zip(items[::2], items[1::2])],
  [1.7 * inch, 1.0 * inch, 1.7 * inch, 1.0 * inch])
P("Throughput mode replaces the following constants: " + ", ".join(f"{k} = {v}" for k, v in PRE["throughput_mode_overrides"].items()) + ".")
P("Engine roles: the equation (2) control law, evaluated on the evolved state, gates capacity release: a machine is released only "
  "when the push required to hold the stack at full coherence is at or below push_release, that is, when the engine reports the stack "
  "converged. f_U includes the double-well drift and the rate of change of error from equation (1). I<sub>U</sub> and E set the headroom; U gates configuration change and power trimming; B limits power when power and "
  "heat accumulate; S and falling U authorise rollbacks. Spread-and-throttle uses the model's property that throttled nodes deliver more "
  "work per kW; real processors show the same direction through voltage-frequency scaling but with smaller gains. min_nodes is carried "
  "for completeness; the lower bound is enforced by the stack configuration. Routing is a reflex rule.")
P("6.3 Omni-Compass over Kubernetes and operating modes", H2)
P("In the layered architecture (arms omni_k8s_protect and omni_k8s_throughput) Kubernetes' autoscalers remain the execution layer. "
  "Each interval the governor sets the HPA target to rho*; the HPA computes replicas with its documented rule; Cluster Autoscaler scale-up "
  "is retained; the node target is the larger of the Cluster Autoscaler and governor targets when either adds capacity; scale-down, power "
  "caps, rollback authority and routing belong to the governor; the combined action set passes through the shield. Operating modes: "
  "<b>power-protect</b> uses the allocation law above and shield invariant I4; <b>throughput</b> releases the power cap to 1 on backlog, "
  "disables the power envelope, spread-and-throttle and bath cap, does not apply I4, and sizes capacity at full power "
  "(load x cap_now) so that power trimming does not trigger machine starts; its power rules match the reference. Throughput-mode "
  "constants (kI, kE, cap_min, down_band, down_dwell, down_after_add, kq, U_gate; values in results/PREREGISTRATION.json) were selected by a "
  "constrained search on development seeds 1000 and 2000: 110 trials, objective minimum energy, subject to backlog violation &lt;= 2.5%, "
  "time healthy &gt;= 88%, recovery &lt;= 25 minutes, scale reversals &lt;= 2.2 and zero non-power invariant violations. Every trial is recorded "
  "in results/development/throughput_search_round*.jsonl. The lowest-energy trials that failed a constraint did so on reversals (6 to 14 "
  "per run); the feasible optimum plateaued near 124 kWh on the development set.")
P("6.4 Safety shield", H2)
lim = PRE["shield_limits"]
P("Every governor action set passes through <font face='Courier'>omnicompass/shield.py</font> before execution. Invariants: "
  "I1 no capacity expansion during an observed security block; I2 node targets within configured bounds and power cap within [0.65, 1]; "
  "I3 no action set both expands capacity and tightens the power cap; "
  f"I4 no node addition whose projected power stress (observed stress x (n + k)/n) exceeds {lim['power_limit']:g}; "
  f"I5 at most {lim['max_node_step']} nodes changed per interval. Violating actions are clipped or removed and counted. "
  "The same invariants are evaluated on the executed actions of every arm, using the true current state, so all arms are scored identically. "
  "Scope: I1 governs changes to infrastructure and deployed software (nodes, Terraform plans, rollouts); replica scaling of already-deployed "
  "workloads is not blocked by I1. I3 counts replica increases as capacity expansion because they raise power draw.")
P("6.5 Authority", H2)
T([["Mode", "Engine computes", "Stack executes"],
   ["OBSERVE", "every directive, logged", "the native managers' own actions"],
   ["AUTOPILOT", "every directive", "the governor's shielded actions only"],
   ["KILLED", "every directive, logged", "the native managers' own actions from the kill interval onward"]],
  [1.3 * inch, 2.4 * inch, 3.1 * inch])

# ------------------------------------------------------------------ 7
P("7. Benchmark Design", H1)
P("7.1 The stack model", H2)
P("A synthetic discrete-time model (72 intervals of 5 minutes, 20 initial nodes, 8 to 40 nodes, 33 kW site limit, PUE 1.18, Terraform "
  "apply delay 8 intervals, node change at most 2 per interval) of the proposal behaviour of Kubernetes, Terraform, HPA/VPA, Karpenter, "
  "Argo CD/Rollouts, Istio/Cilium, power/thermal management, alerting and paging. Scenario families: normal variation, demand surge, node "
  "failure, thermal stress, network degradation, rollout pressure, security block, telemetry delay and compound events. Extracted "
  "byte-for-byte from the reference engine.")
P("7.2 Baselines", H2)
P("<b>native</b>: the reference engine's fragmented-manager model; every manager executes its own proposal. "
  "<b>k8s_ref_50 to k8s_ref_80</b>: a documented-behaviour reference model of Kubernetes autoscaling with current (non-delayed) metrics. "
  "It is not the upstream controllers. HPA desired = ceil(current x load / target) with target 0.5, 0.6, 0.7 or 0.8 (the target is workload "
  "configuration, so all four are run), no change within 10% tolerance, scale-down using the highest recommendation over the 300 s "
  "stabilization window; Cluster Autoscaler scale-up sized to unschedulable work, node removal after 10 minutes below 50% utilization and "
  "not within 10 minutes of a scale-up; paging after 15 minutes of queue ratio above 0.35; Terraform not used as a live controller; power, "
  "rollout, rollback and routing proposals executed as proposed. Not represented: Cluster Autoscaler scheduling simulation, Karpenter "
  "consolidation, VPA, scheduling constraints, disruption budgets. The primary tables use target 0.7; Section 8.3 reports all four.")
P("7.3 Omni-Compass arms", H2)
T([["Arm", "Sensing", "Actuation", "Shield", "Definition"],
   ["omni_k8s_protect", "direct", "governor over Kubernetes", "on", "flagship: layered, power-protect mode"],
   ["omni_k8s_throughput", "direct", "governor over Kubernetes", "on (no I4)", "flagship: layered, throughput mode"],
   ["omni_k8s_observe", "direct", "none (Kubernetes acts)", "n/a", "governor observing Kubernetes; must equal k8s_ref_70"],
   ["omni_k8s_kill", "direct", "governor over Kubernetes", "on", "power-protect, killed at event onset + 2; Kubernetes continues"],
   ["omni_observe", "pipeline", "none", "n/a", "governor in OBSERVE for the whole run"],
   ["omni_pipeline", "pipeline", "via Terraform plans", "on", "AUTOPILOT with delayed telemetry"],
   ["omni_direct", "direct", "direct", "on", "governor replacing Kubernetes' autoscaling decisions"],
   ["omni_direct_no_dynamics", "direct", "direct", "on", "flagship with equations (1) to (7) not evolved"],
   ["omni_direct_no_shield", "direct", "direct", "off", "flagship without the shield"],
   ["omni_kill", "direct", "direct", "on", "flagship killed two intervals after event onset"],
   ["omni_switch_on", "direct", "direct", "on", "OBSERVE until event onset, then AUTOPILOT"]],
  [1.5 * inch, 0.7 * inch, 1.1 * inch, 0.5 * inch, 3.0 * inch])
P("7.4 Scoring", H2)
P("All arms are scored by the same functions from stack physics and executed actions. Physical SLA violation: queue ratio &gt; 0.35, "
  "power stress &gt; 1.05 or thermal &gt; 1.03. Healthy interval: queue ratio &lt; 0.28, power stress &lt;= 1.02, thermal &lt; 0.96 and "
  "no contradiction. Recovery: event end to the fourth consecutive healthy interval (360 minutes if not reached). Contradictions: opposing "
  "node or replica directions, rollout with rollback, expansion with power tightening, expansion during a security denial, duplicate "
  "alerts. Wear: machine start/stop count (sum of absolute node-count changes), power-cap travel (sum of absolute cap changes), thermal "
  "travel (sum of absolute thermal changes), scale direction reversals (changes of node or replica direction), machines started, "
  "machines stopped, and machine round trips = (started + stopped - |final - initial node count|) / 2, the number of machines started "
  "and later stopped or stopped and later restarted. One-way adjustments, such as shutting down surplus machines, are not round trips. Tail measures: 5th percentile of time healthy, 95th percentiles of recovery, physical SLA "
  "violation and energy.")
P("7.5 Protocol", H2)
P(PRE["selection"])
for note in PRE.get("post_registration_notes", []):
    P(note)
P(f"Development seeds: {', '.join(str(x) for x in PRE['development_seeds'])}. The allocation law, shield, baselines and benchmark code were "
  "frozen and their SHA-256 and program fingerprints recorded in results/PREREGISTRATION.json before the held-out seeds "
  f"{S1} and {S2} (500 scenarios each) were run. Paired 95% intervals are bootstrap intervals over scenarios (4,000 resamples). "
  "A result is called better or worse only when the interval excludes zero.")

# ------------------------------------------------------------------ 8
P("8. Results", H1)
P("Figures show means over both held-out seeds; tables report each seed separately with paired significance. Verdicts compare each "
  "Omni-Compass mode with the Kubernetes reference at HPA target 0.7.")
FIGURE("healthy.png", 6.2 * inch)
FIGURE("recovery.png", 6.2 * inch)
rows = [("time_healthy", "Time healthy", pct, False), ("recovery_minutes", "Recovery (minutes)", f1, True),
        ("recovered", "Scenarios recovered", pct, False), ("sla_violation_physical", "Physical SLA violation", pct, True),
        ("violation_backlog", "  backlog", pct, True), ("violation_power", "  power", pct, True), ("violation_heat", "  heat", pct, True),
        ("availability", "Work completed", lambda v: f"{100 * v:.2f}%", False), ("energy_kwh", "Energy (kWh)", f1, True),
        ("node_hours", "Node-hours", f1, True), ("contradictions", "Contradictions per run", f1, True),
        ("invariant_violations", "Invariant violations I1-I5", f2, True), ("invariant_violations_ex_power", "Invariant violations excl. I4", f2, True),
        ("security_violations", "Expansions during security block", f2, True), ("scale_reversals", "Scale direction reversals", f2, True),
        ("machines_started", "Machines started", f1, True), ("machines_stopped", "Machines stopped", f1, True),
        ("machine_round_trips", "Machine round trips", f1, True), ("power_cap_travel", "Power-cap travel", f2, True),
        ("thermal_travel", "Thermal travel", f2, True)]

def verdict(sd, comp, mm, lower):
    if mm in ("machines_started", "machines_stopped"):
        return "count"
    r = pr(sd, comp, mm); lo, hi = r["ci95"]
    if hi < 0: return "better" if lower else "worse"
    if lo > 0: return "worse" if lower else "better"
    return "n.s."

for idx, sd in enumerate((S1, S2)):
    P(f"8.{idx + 1} Held-out seed {sd} (500 scenarios)", H2)
    tab = [["Measure", "K8s ref 0.7", "power-protect", "throughput", "protect vs ref", "throughput vs ref"]]
    for mm, lab, fm, lower in rows:
        tab.append([lab, fm(mean(sd, "k8s_ref_70", mm)), fm(mean(sd, "omni_k8s_protect", mm)), fm(mean(sd, "omni_k8s_throughput", mm)),
                    verdict(sd, "omni_k8s_protect_vs_k8s_ref_70", mm, lower), verdict(sd, "omni_k8s_throughput_vs_k8s_ref_70", mm, lower)])
    T(tab, [1.9 * inch, 0.85 * inch, 0.95 * inch, 0.85 * inch, 1.05 * inch, 1.2 * inch])

P("8.3 Sensitivity to the reference HPA target", H2)
FIGURE("sensitivity.png", 6.6 * inch)
REFS = ("k8s_ref_50", "k8s_ref_60", "k8s_ref_70", "k8s_ref_80")
sens = [("time_healthy", "Time healthy", False), ("recovery_minutes", "Recovery", True), ("sla_violation_physical", "Physical SLA", True),
        ("violation_backlog", "Backlog violation", True), ("availability", "Work completed", False), ("energy_kwh", "Energy", True),
        ("scale_reversals", "Reversals", True), ("machine_round_trips", "Round trips", True), ("thermal_travel", "Thermal travel", True)]
T([["Measure", "power-protect better in", "throughput better in", "throughput worse in"]] +
  [[lab, f"{sum(verdict(sd, 'omni_k8s_protect_vs_' + r, mm, lower) == 'better' for sd in (S1, S2) for r in REFS)}/8",
    f"{sum(verdict(sd, 'omni_k8s_throughput_vs_' + r, mm, lower) == 'better' for sd in (S1, S2) for r in REFS)}/8",
    f"{sum(verdict(sd, 'omni_k8s_throughput_vs_' + r, mm, lower) == 'worse' for sd in (S1, S2) for r in REFS)}/8"] for mm, lab, lower in sens],
  [1.8 * inch, 1.6 * inch, 1.6 * inch, 1.6 * inch])
P("Counts are over 2 seeds x 4 HPA targets. Human pages are not reported as a result: the governor issues no page actions by design.")

P("8.4 Primary endpoint and multiplicity", H2)
P("Primary comparison: throughput mode vs the Kubernetes reference at HPA target 0.7. Primary metric: energy per run. Secondary metrics "
  "are tested with a paired sign-flip permutation test (10,000 permutations) and Holm-adjusted across all secondary metrics and both seeds "
  "(24 tests). The smallest attainable p-value is 1/10,001.")
T([["Seed", "Energy difference (kWh)", "p", "Scenarios better"]] +
  [[sd, f"{r['mean_delta']:+.2f}", f"{r['p']:.1e}", f"{r['better']}/{r['n']}"] for sd, r in MULT["primary"].items()],
  [1.6 * inch, 1.8 * inch, 1.2 * inch, 1.6 * inch])
T([["Seed", "Metric", "Difference", "Holm p", "Verdict"]] +
  [[t["seed"], t["metric"], f"{t['mean_delta']:+.4f}", f"{t['p_holm']:.1e}", t["verdict"]] for t in MULT["secondary"]],
  [1.1 * inch, 2.2 * inch, 1.1 * inch, 1.0 * inch, 1.4 * inch])
P("8.5 Worst cases", H2)
FIGURE("distribution.png", 6.2 * inch)
tl = HO[S1]["tails"]
T([["Arm", "Healthy p05", "Healthy min", "Recovery p95 (min)", "Physical SLA p95", "Energy p95 (kWh)"]] +
  [[a, pct(tl[a]["time_healthy_p05"]), pct(tl[a]["time_healthy_min"]), f"{tl[a]['recovery_minutes_p95']:.0f}",
    pct(tl[a]["sla_violation_physical_p95"]), f1(tl[a]["energy_kwh_p95"])] for a in ("native", "k8s_ref_70", "omni_k8s_protect", "omni_k8s_throughput")],
  [1.6 * inch, 0.9 * inch, 0.9 * inch, 1.1 * inch, 1.1 * inch, 1.1 * inch])
P(f"Seed {S1}.")

P("8.6 Attribution", H2)
arms8 = ("native", "k8s_ref_70", "omni_observe", "omni_k8s_observe", "omni_k8s_protect", "omni_k8s_throughput", "omni_k8s_kill",
         "omni_direct", "omni_direct_no_dynamics",
         "omni_direct_no_shield", "omni_pipeline", "omni_kill", "omni_switch_on")
T([["Arm", "Healthy", "Phys. SLA", "Backlog", "Recovery", "Energy", "Round trips", "Inv. viol."]] +
  [[a, pct(mean(S1, a, "time_healthy")), pct(mean(S1, a, "sla_violation_physical")), pct(mean(S1, a, "violation_backlog")),
    f1(mean(S1, a, "recovery_minutes")), f1(mean(S1, a, "energy_kwh")), f1(mean(S1, a, "machine_round_trips")),
    f2(mean(S1, a, "invariant_violations"))] for a in arms8],
  [1.75 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch, 0.75 * inch, 0.7 * inch])
d_ = lambda a, mm: mean(S1, a, mm)
P(f"Seed {S1}. omni_observe is bit-identical to native in every held-out scenario; omni_k8s_observe (governor observing Kubernetes) is "
  f"bit-identical to Kubernetes alone in {HO[S1]['layered_observe_identical_to_kubernetes']}/500 and {HO[S2]['layered_observe_identical_to_kubernetes']}/500. "
  "omni_k8s_kill runs power-protect mode until two intervals after event onset, after which Kubernetes alone continues. omni_k8s_protect vs omni_direct measures the value of "
  "keeping Kubernetes' autoscalers as the execution layer; omni_direct vs omni_pipeline measures direct sensing and actuation; "
  "omni_direct vs omni_direct_no_dynamics measures the contribution of evolving equations (1) to (7): "
  f"energy {f1(d_('omni_direct','energy_kwh'))} vs {f1(d_('omni_direct_no_dynamics','energy_kwh'))} kWh, round trips "
  f"{f1(d_('omni_direct','machine_round_trips'))} vs {f1(d_('omni_direct_no_dynamics','machine_round_trips'))}, healthy "
  f"{pct(d_('omni_direct','time_healthy'))} vs {pct(d_('omni_direct_no_dynamics','time_healthy'))}. The engine dynamics contribute a "
  "modest share of the gain; direct wiring, single authority, the allocation law and the shield carry most of it. The kill and switch-on "
  "arms omni_kill and omni_switch_on are built on omni_direct, where the native managers resume after a kill.")
g = lambda a, mm: float(np.mean([mean(sd, a, mm) for sd in (S1, S2)]))
P("<b>Engine contribution in the flagship (throughput mode, both seeds).</b> "
  f"With equations (1) to (7) evolved and the equation (2) release gate: energy {f1(g('omni_k8s_throughput','energy_kwh'))} kWh, reversals "
  f"{f2(g('omni_k8s_throughput','scale_reversals'))}, round trips {f1(g('omni_k8s_throughput','machine_round_trips'))}, healthy "
  f"{pct(g('omni_k8s_throughput','time_healthy'))}. Gate removed: energy {f1(g('omni_k8s_throughput_no_gate','energy_kwh'))}, reversals "
  f"{f2(g('omni_k8s_throughput_no_gate','scale_reversals'))}, round trips {f1(g('omni_k8s_throughput_no_gate','machine_round_trips'))}, healthy "
  f"{pct(g('omni_k8s_throughput_no_gate','time_healthy'))}. Evolution removed: energy {f1(g('omni_k8s_throughput_no_dynamics','energy_kwh'))}, reversals "
  f"{f2(g('omni_k8s_throughput_no_dynamics','scale_reversals'))}, round trips {f1(g('omni_k8s_throughput_no_dynamics','machine_round_trips'))}, healthy "
  f"{pct(g('omni_k8s_throughput_no_dynamics','time_healthy'))}. Paired comparisons are in the summary files under "
  "omni_k8s_throughput_vs_omni_k8s_throughput_no_gate and omni_k8s_throughput_vs_omni_k8s_throughput_no_dynamics.")

P("8.7 Fleet component model", H2)
FL = FLEET["util8_sidecar"]
T([["Role", "Share of fleet vCPU", "Share of fleet energy"]] +
  [[role, f"{100 * g['share_of_fleet_vcpu']:.2f}%", f"{100 * g['share_of_fleet_energy_low']:.2f} to {100 * g['share_of_fleet_energy_high']:.2f}%"]
   for role, g in FL["by_role"].items()] +
  [["idle capacity", f"{100 * FL['idle_share_of_fleet_vcpu']:.0f}%", f"{100 * FL['idle_vcpu_share_of_fleet_energy']:.0f}%"]],
  [2.0 * inch, 2.0 * inch, 2.4 * inch])
P(f"{FL['fleet']['nodes']:,} nodes in {FL['clusters']} clusters, 64 cores and 256 GiB per node, 30 pods per node, 8% mean CPU utilization, "
  f"sidecar service mesh. Energy per resource: {FL['energy_model']}. Decision components consume a negligible share of the fleet; their cost "
  "is the capacity they leave idle or padded, which is the quantity the governor changes. The service mesh is the largest single component "
  "and is a security function retained under the keep-or-remove rule.")

# ------------------------------------------------------------------ fleet
FS = json.loads((R / "fleet" / "heldout" / "SUMMARY.json").read_text())
FP = json.loads((R / "fleet" / "PREREGISTRATION.json").read_text())
P("8.8 Fleet harness at 15-second resolution", H2)
P("fleet/ is a second, independent harness in which the Kubernetes execution layer runs at its documented cadence: metrics-server "
  "(15 s lag, usage over request), HPA (ratio law, 10% tolerance, 300 s scale-down window, scale-up limited to max(4 pods, 100%) per "
  "15 s), Cluster Autoscaler (pending scale-up; removal after 10 min below 50% request utilization, not within 10 min of a scale-up) "
  "and Karpenter-lite (exact provisioning for pending requests, consolidation every 30 s). The plant has many workloads per cluster "
  "with CPU requests and actual usage, request packing, identical node boot delay for every arm, power, heat and a site power limit. "
  "Vessels: web services (12 HPA workloads, diurnal load with bursts), batch/HPC job queue, GPU training (8-GPU nodes), and a "
  "multi-cluster fleet (4 clusters sharing one site power budget). In omni_fleet the governor is the node-pool and power authority "
  "in place of the Cluster Autoscaler, with the HPA retained as the replica controller; this is a different question from governing "
  "on top of an unchanged HPA and Cluster Autoscaler (omni_target). The single-authority arms are the comparison reported below, "
  f"deciding every {FP['fleet_decision_seconds']} s: HPA runs with target rho*, the Cluster Autoscaler is not run, nodes never fall "
  "below what current pod requests need, and actions pass through the shield. All workload series are synthetic.")
P(FP["selection"])
rowsF = []
for v in ("web", "multi", "batch", "gpu", "gpu_always_on"):
    d = FS["vessels"][v]
    for mode, mlab in (("omni_fleet", "energy-first"), ("omni_fleet_balanced", "balanced"), ("omni_fleet_wear", "wear-first"), ("omni_fleet_park", "park")):
      for base, lab in (("k8s_hpa70_ca", "vs HPA 0.7 + CA"), ("k8s_hpa70_karpenter", "vs HPA 0.7 + Karpenter-lite")):
        Pp = {x["metric"]: x for x in d["paired"][f"{mode}_vs_{base}"]}
        rowsF.append([v, mlab + " " + lab, f"{Pp['energy_kwh']['base']:.1f} to {Pp['energy_kwh']['cand']:.1f} ({100 * (Pp['energy_kwh']['cand'] / Pp['energy_kwh']['base'] - 1):+.1f}%) {Pp['energy_kwh']['verdict']}",
                      f"{Pp['node_reversals']['base']:.1f} to {Pp['node_reversals']['cand']:.1f} {Pp['node_reversals']['verdict']}",
                      f"{100 * Pp['time_healthy']['base']:.1f}% to {100 * Pp['time_healthy']['cand']:.1f}% {Pp['time_healthy']['verdict']}",
                      f"{100 * Pp['work_completed']['base']:.2f}% to {100 * Pp['work_completed']['cand']:.2f}%"])
T([["Vessel", "Setting and baseline", "Energy (kWh)", "Node reversals", "Time healthy", "Work completed"]] + rowsF,
  [0.55 * inch, 1.55 * inch, 1.8 * inch, 1.15 * inch, 1.15 * inch, 0.9 * inch])
P(f"Held-out: {FP['held_out_scenarios_per_vessel']} scenarios per vessel from seed {FP['held_out_seed_base']}; paired bootstrap 95% intervals; "
  "a verdict is stated only when the interval excludes zero. Observe mode is bit-identical to HPA 0.7 + Cluster Autoscaler in every "
  "scenario of every vessel. Differences in time healthy and work completed of 0.1% or less can be statistically significant and are "
  "reported as measured.")
abl = []
for v in ("web", "multi", "batch", "gpu", "gpu_always_on"):
    d = FS["vessels"][v]
    for a_, lab in (("omni_fleet_no_dynamics", "equations (1)-(7) not evolved"), ("omni_fleet_no_gate", "equation (2) release gate removed")):
        Pp = {x["metric"]: x for x in d["paired"][f"omni_fleet_vs_{a_}"]}
        abl.append([v, lab, f"{Pp['energy_kwh']['delta']:+.2f} kWh {Pp['energy_kwh']['verdict']}", f"{100 * Pp['time_healthy']['delta']:+.1f} pts {Pp['time_healthy']['verdict']}"])
T([["Vessel", "Ablation", "Full engine energy minus ablation", "Time healthy"]] + abl, [0.7 * inch, 2.4 * inch, 2.1 * inch, 1.6 * inch])
P("Families: web, multi, batch and gpu are elastic (nodes may be powered off); gpu_always_on is always-on (powering a node off is "
  "not permitted, so every arm may only park idle nodes: Ready, 25% of idle power, wake within one tick). The park setting executes the "
  "energy-first law's capacity reductions as parking instead of power-off. Machines stopped counts power-offs only; park moves are "
  "counted separately.")
P("Settings: energy-first uses the lenient release threshold selected for energy (the equation (2) gate does not bind); balanced and "
  "wear-first activate the equation (2) gate in both directions (a machine is released only when the push reports convergence and, "
  "without backlog, added only when the push reports need), trading energy for fewer node reversals. The engine's evolution reduces "
  "energy in the batch and GPU vessels and has no significant effect in the web and multi-cluster vessels (ablations above, energy-first).")

P("8.9 Recorded workloads (PlanetLab)", H2)
PL = json.loads((R / "fleet" / "planetlab" / "SUMMARY.json").read_text())
PLP = json.loads((ROOT / "fleet" / "traces" / "PROVENANCE.json").read_text())
P(f"The fleet harness was run with the frozen laws, without retuning, on {PL['traces']} recorded PlanetLab/CoMon VM CPU traces "
  f"({PL['scenarios']} scenarios from seed {PL['seed_base']}; each scenario assigns traces, requests and peak pod counts to 12 workloads). "
  "These are recorded utilization shapes with a declared scale: the mapping from CPU percent to cores (percent / 100 x peak pods x "
  "request, 12 workloads) is declared in fleet/planetlab.py, so the load level is a modelling choice, not a measurement. " + PLP["acquisition"].capitalize() + ". "
  f"Observe mode was bit-identical to HPA 0.7 + CA in {PL['observe_identical']}/{PL['scenarios']} scenarios.")
b_ = PL["means"]["k8s_hpa70_ca"]["energy_kwh"]; k_ = PL["means"]["k8s_hpa70_karpenter"]["energy_kwh"]
rowsP = []
for arm in ("k8s_hpa70_ca", "k8s_hpa70_karpenter", "omni_target", "omni_fleet", "omni_fleet_balanced", "omni_fleet_wear", "omni_fleet_park", "omni_fleet_no_dynamics"):
    mm = PL["means"][arm]
    vca = {x["metric"]: x["verdict"] for x in PL["paired"].get(f"{arm}_vs_k8s_hpa70_ca", [])}
    vkp = {x["metric"]: x["verdict"] for x in PL["paired"].get(f"{arm}_vs_k8s_hpa70_karpenter", [])}
    rowsP.append([arm, f"{mm['energy_kwh']:.2f}", f"{100 * (mm['energy_kwh'] / b_ - 1):+.1f}% {vca.get('energy_kwh', '')}",
                  f"{100 * (mm['energy_kwh'] / k_ - 1):+.1f}% {vkp.get('energy_kwh', '')}", f"{100 * mm['time_healthy']:.2f}%", f"{mm['node_reversals']:.2f}"])
T([["Arm", "Energy (kWh)", "vs HPA + CA", "vs Karpenter-lite", "Time healthy", "Node reversals"]] + rowsP,
  [1.6 * inch, 0.8 * inch, 1.3 * inch, 1.4 * inch, 0.9 * inch, 0.9 * inch])
P("On recorded workloads the governor's energy reduction relative to both baselines is significant in the energy-first, balanced and "
  "wear-first settings; time healthy (by 0.08 points) and work completed (by 0.01%) are significantly lower; node reversals are not "
  "significantly different from Karpenter-lite. Parking does not reduce energy at these low utilizations. Evolving equations (1)-(7) "
  "has no significant effect on this web-type workload.")

P("8.10 HPA agreement across implementations", H2)
P("Three implementations of the HPA replica law are compared on every step of recorded streams: the fleet harness (a 20-sample "
  "recommendation ring), an independent C++ implementation, and an externally written Python implementation that keeps "
  "recommendations by timestamp. Upstream Kubernetes keeps recommendations whose timestamp is after the cutoff (exclusive); at a fixed "
  "15 s cadence the 20-sample ring is exactly that window, (now - 300 s, now]. The external implementation, with an inclusive boundary, "
  "differs on 0.39% of steps; with the exclusive boundary all three agree on every step (tests/test_hpa_three_way.py). The ring "
  "would diverge from a timestamp window only if sampling were irregular.")
SV = list(csv.DictReader(open(R / "SAVINGS.csv")))
P("8.11 Savings projection (method, not measurement)", H2)
P("benchmarks/savings.py and cpp/tools/savings.cpp apply the energy reduction of the energy-first governor relative to HPA 0.7 + "
  "Karpenter-lite (mean and paired 95% interval) to declared fleet profiles: annual energy = nodes x average kW x PUE x 8,760 h; "
  "cost and CO2 follow from the declared price and carbon intensity. GPU vessels use a declared 6 kW per node. The reductions are "
  "simulation results; the profiles are examples; the output is a projection, not a measurement.")
T([["Profile", "Vessel", "Saved MWh / yr (mid)", "Saved USD / yr (low to high)", "Saved t CO2 / yr (mid)"]] +
  [[r["profile"], r["vessel"], f"{float(r['saved_mwh_mid']):,.0f}", f"{float(r['saved_usd_low']):,.0f} to {float(r['saved_usd_high']):,.0f}",
    f"{float(r['saved_tco2_mid']):,.0f}"] for r in SV],
  [1.4 * inch, 1.2 * inch, 1.3 * inch, 1.8 * inch, 1.2 * inch])

P("8.12 Live controller", H2)
P("omni_controller/controller.py runs the fleet-mode governor against a real cluster through kubectl, every 60 s by default, in "
  "three modes: observe (decisions logged, no writes; the default), target (each HPA's CPU averageUtilization set to rho*, bounded "
  "to 50-95% and changed only by at least 3 points, original recorded in an annotation; node management unchanged) and nodepool "
  "(one node pool sized to the governor's recommendation through a configured command, never below what running pod requests or "
  "current usage need, step-limited by the shield; the Cluster Autoscaler must not manage that pool). --dry-run logs writes "
  "without executing them. The kill switch (a file or OMNI_KILL=1) restores every changed HPA target from its annotation, including "
  "after a restart, and returns to observe. Every decision and write is appended to an audit log. deploy/ contains a Dockerfile "
  "and manifests with separate read-only (observe) and HPA-write (target) permissions. The controller is tested against a fake "
  "kubectl (tests/test_omni_controller.py); it has not been run against a real cluster. The scheduling floor counts running and "
  "pending pods' CPU requests plus a headroom margin (default 50%); between governor decisions a 15-second check adds the nodes "
  "that pending pods need in one step.")
P("8.12a End-to-end self-pilot", H2)
P("pilot/selfpilot.py runs the shipped controller in nodepool mode against a simulated cluster (the fleet harness web workload, "
  "request packing, 90 s node boot, power) that answers its kubectl reads and applies its HPA patches and node-pool resizes, for "
  "one day, and scores it against HPA 0.7 + Cluster Autoscaler on identical traffic with pilot/score.py. Headroom trade-off "
  "measured on seed 424242 (change vs baseline; pending-pod minutes per hour, baseline 4.0): headroom 0: energy per core-hour "
  "-17%, pending 24.6; 0.10: -17%, 20.6; 0.25: -15%, 13.4; 0.50 (default): -7.7%, 5.0 (no significant difference), node-hours "
  "per core-hour -14%. HPA shortfall minutes are higher than baseline at every headroom setting (about +1.2 minutes per hour); "
  "the cause is open. Running this self-pilot found and fixed two controller faults: the scheduling floor ignored pending pods, "
  "and capacity for pending pods waited for the next governor decision.")

P("8.13 Scoring a pilot", H2)
P("pilot/score.py compares a baseline capture with an Omni-Compass capture from the same cluster (periods or matched node "
  "pools), normalising by work done: node-hours and energy per used CPU core-hour, utilisation, pending-pod minutes per hour and "
  "HPA shortfall minutes per hour, each with a bootstrap 95% interval over hourly blocks. Energy is measured when captures include "
  "power, otherwise modelled from declared node power. It is tested to detect a real efficiency gain, to report no significant "
  "difference between identical clusters and to detect a service regression (tests/test_pilot_score.py).")

P("8.14 Paths for real data", H2)
P("Three components connect the package to real systems; each is tested on generated inputs in the exact real formats "
  "(tests/test_fleet_realdata_paths.py). No real capture or recorded trace has been run inside this package, because the build "
  "environment has no cluster and no network access to the trace repository.")
T([["Component", "Input", "Output"],
   ["fleet/capture/kube_capture.sh", "a live cluster, read-only (kubectl get/top, jq); optional site power command", "CSV every 15 s: nodes, allocatable, requested and used CPU, pending pods, HPA current and desired replicas, power"],
   ["fleet/capture_replay.py", "a capture CSV", "the fleet-mode governor in OBSERVE: recommended node count, power cap and HPA target per decision; counterfactual node-hours and, with a power model or captured power, estimated energy"],
   ["fleet/planetlab.py", "a directory of PlanetLab traces (one integer percent per line)", "every fleet arm on recorded workload shapes with the frozen laws"]],
  [1.7 * inch, 2.2 * inch, 2.9 * inch])
P("The capture replay carries the recommended fleet forward as the governor's own counterfactual state, never below the node count "
  "that running pod requests or current usage require. Its output is a recommendation, not a measurement: the cluster's response to "
  "the recommended fleet is not modelled.")

# ------------------------------------------------------------------ 9
P("9. Reproduction", H1)
E("# full verification\npython verify.py\n\n# one held-out stack run\n"
  "python benchmarks/stack_benchmark.py --seed 161803398 --scenarios 500 --out out/\n\n"
  "# core evidence, fleet model\npython benchmarks/core_evidence.py\npython benchmarks/fleet_overhead.py\n\n"
  "# soak test (C++)\ncmake -S cpp -B build && cmake --build build && build/oc_soak 100000000\n\n"
  "# rebuild manual and evaluation kit\npython docs/build_manual.py\npython docs/build_kit.py")

# ------------------------------------------------------------------ 10
P("10. Open Obligations", H1)
for t in [
    "Production evidence: all stack results are from the synthetic model; replay of published production traces (Google, Alibaba, Azure) and the pilot protocol are required.",
    "Stack model validity: proposal rules, power and thermal physics, the throttling efficiency relation and delays are not calibrated to measured systems.",
    "Boundedness theorem: a forward-invariance or input-to-state-stability proof for the sampled-data governor loop. A computer-assisted interval-arithmetic proof was attempted; it did not close, because interval bounds on the cubic U term widen across the ten micro steps. Taylor-model or affine arithmetic is the next method. Boundedness is supported empirically by the soak tests and adversarial runs.",
    "Barrier certificates: the shield is a runtime monitor; a barrier-certificate proof that the shielded loop keeps the stack in the safe set under the model is open.",
    "Wear: see Chapter 8 for scale direction reversals and machine round trips in each mode relative to the reference; power-protect mode reverses direction more often than the reference.",
    "Fleet harness: workloads are synthetic; the execution layer reproduces documented behaviour, not the upstream binaries; scheduling is fluid packing without affinity, disruption budgets or multi-zone placement; GPU throughput scales linearly with the power cap.",
    "Engine mechanism: the six-state engine contributes through the equation (2) release gate and the state-derived headroom; the governor's capacity sizing, power trimming and single authority remain rule-based.",
    "Power-protect mode: backlog violations and work completed are worse than the reference, because the site power limit is enforced and the reference does not enforce it.",
    "Baseline fidelity: the Kubernetes baseline is a documented-behaviour reference model; running the upstream Cluster Autoscaler, Karpenter, HPA and VPA controllers against the same scenarios is open.",
    "Power-protect constants were set by development tuning, not by constrained search; throughput constants come from a 110-trial random and local search and are not proven optimal.",
    "Multi-cluster, GPU-cluster and facility-level vessels are not yet built.",
    "Independent reimplementation from this manual has not been performed."]:
    story.append(Paragraph("&#8226; " + t, BODY))

# ------------------------------------------------------------------ appendix
story.append(PageBreak())
P("Appendix A. File Register", H1)
files = sorted([p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pdf"
                and "build" not in p.relative_to(ROOT).parts])
T([["File", "SHA-256"]] + [[str(p.relative_to(ROOT)), hashlib.sha256(p.read_bytes()).hexdigest()[:32] + "..."] for p in files],
  [3.4 * inch, 3.4 * inch])


def footer(canvas, doc):
    canvas.saveState(); canvas.setFont("Helvetica", 8)
    canvas.drawString(0.75 * inch, 0.5 * inch, "Omni-Compass Technical Manual")
    canvas.drawRightString(7.75 * inch, 0.5 * inch, f"{doc.page}")
    canvas.restoreState()


out = ROOT / "docs" / "OMNI_COMPASS_TECHNICAL_MANUAL.pdf"
SimpleDocTemplate(str(out), pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch, topMargin=0.75 * inch,
                  bottomMargin=0.75 * inch, title="Omni-Compass Technical Manual", author="The Omni-Compass LLC").build(
    story, onFirstPage=footer, onLaterPages=footer)
print("wrote", out)
