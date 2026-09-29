"""The Omni-Compass plate, rebuilt to match the running engine.

  python3 docs/plate/build_plate.py   ->  docs/plate/OMNI_COMPASS_PLATE.png and .pdf

The eight lines are the equation block the original engine prints (docs/handoff/mathematics/
omni_compass_engine_source_c527df2d.py, lines 150-166), identical to omnicompass/core.py, cpp/src/core.cpp and
paragraph [0085] of the patent application. The symbol chart lists every symbol those eight lines use; it replaces
the original chart, which still listed the retired logistic form's alpha and k and omitted mu, lambda_U, lambda_I,
alpha_E, chi, u and U_AUTHORITY.
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

OUT = Path(__file__).resolve().parent
plt.rcParams.update({"font.family": "DejaVu Serif", "mathtext.fontset": "dejavuserif"})

EQS = [
    r"$\dfrac{dE}{dt} = -\alpha_E E + \beta_{\mathrm{int}}(t) + \beta_{\mathrm{ext}}(t) + v_{\mathrm{eff}}$",
    r"$\dfrac{dU}{dt} = \mu U(1-U^2) - \dfrac{dE/dt}{E_{\max}} - \lambda_U U + u,\quad |u| \leq U_{\mathrm{AUTHORITY}}$",
    r"$\dfrac{dI_U}{dt} = 1 - U - \sigma_1 E - \delta S - \lambda_I I_U$",
    r"$v_{\mathrm{eff}} = \chi(t)\,c\,\tanh[\lambda_0 + \lambda_1(U-U_t) + \lambda_2 S],\quad \chi(t)=\cos(\omega_B t/2)$",
    r"$\Phi(S) = \frac{1}{2}\alpha_s S^2 + \frac{1}{4}\beta_s S^3 - \delta S$",
    r"$\partial S = F_{\mathrm{state}}(S) = -\dfrac{\partial\Phi(S)}{\partial S} = \delta - \alpha_s S - \frac{3}{4}\beta_s S^2$",
    r"$\partial^2 B + \dfrac{\omega_B}{Q_B}\partial B + \omega_B^2 B = \gamma_c \delta S$     [continuous]",
    r"$R_B[n] = D_h^2 B[n] + \dfrac{\omega_B}{Q_B} D_h^{-} B[n] + \omega_B^2 B[n] - \gamma_c\delta S[n] = 0$     [discrete audit]",
]
SYMS = [
    (r"$E$", "Error / misalignment\nenergy"), (r"$U$", "Coherence / alignment\nindex"),
    (r"$I_U$", "Information / internal-\ncoherence channel"), (r"$S$", "Coherence-state\npotential"), (r"$B$", "Bath field"),
    (r"$B_{\mathrm{dot}}$", "Bath-field time\nderivative"), (r"$\alpha_E$", "E-channel decay /\nfeedback rate"),
    (r"$\beta_{\mathrm{int}}(t)$", "Internal forcing\nfunction"), (r"$\beta_{\mathrm{ext}}(t)$", "External forcing\nfunction"),
    (r"$v_{\mathrm{eff}}$", "Bounded effective\ndrive"),
    (r"$\mu$", "Bistable (double-well)\nstrength"), (r"$\lambda_U$", "U-channel damping"),
    (r"$u$", "Bounded supervisory\ncommand"), (r"$U_{\mathrm{AUTHORITY}}$", "Command authority\nbound"),
    (r"$E_{\max}$", "Per-trajectory error-rate\nnormalization"),
    (r"$\sigma_1$", r"E-coupling into $I_U$"), (r"$\delta$", "Linear coherence\ncoupling parameter"),
    (r"$\lambda_I$", r"$I_U$ damping"), (r"$\chi(t)$", r"Phase multiplier" + "\n" + r"$\cos(\omega_B t/2)$"), (r"$c$", "Limiting velocity"),
    (r"$\lambda_0$", "Saturation bias"), (r"$\lambda_1$", "Saturation gain"), (r"$\lambda_2$", "S-state coupling gain"),
    (r"$U_t$", "Target coherence state"), (r"$\Phi(S)$", "Potential-field\nfunction"),
    (r"$F_{\mathrm{state}}(S)$", "Canonical S-state flow"), (r"$\alpha_s$", "S-potential quadratic\ncoefficient"),
    (r"$\beta_s$", "S-potential cubic\ncoefficient"), (r"$\omega_B$", "Bath angular frequency"), (r"$Q_B$", "Bath quality factor"),
    (r"$\gamma_c$", "Bath coupling gain"), (r"$R_B[n]$", "Discrete bath residual\n(audit)"),
    (r"$D_h^2$", "Centered second\ndifference"), (r"$D_h^{-}$", "Backward first\ndifference"), (r"$h$", "Microstep size"),
]


def build():
    fig = plt.figure(figsize=(8.5, 11)); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 8.5); ax.set_ylim(0, 11); ax.axis("off")
    ax.add_patch(Rectangle((0.15, 0.15), 8.2, 10.7, fill=False, lw=2.2))
    ax.text(4.25, 10.42, "THE OMNI-COMPASS UNIFIED GOVERNING\nCONVERGENCE CONTROL CORE ENGINE", ha="center", va="center",
            fontsize=19, fontweight="bold", linespacing=1.15)
    # equation form
    top, row = 9.85, 0.48
    ax.add_patch(Rectangle((0.4, top - 0.55 - 8 * row - 0.12), 7.7, 0.55 + 8 * row + 0.12, fill=False, lw=0.9))
    ax.text(4.25, top - 0.27, "THE OMNI-COMPASS EQUATION FORM", ha="center", va="center", fontsize=13.5, fontweight="bold")
    y0 = top - 0.55
    ax.plot([0.5, 8.0], [y0, y0], lw=0.7, color="k")
    for i, eq in enumerate(EQS):
        yc = y0 - (i + 0.5) * row
        ax.text(0.78, yc, str(i + 1), ha="center", va="center", fontsize=13, fontweight="bold")
        ax.text(1.18, yc, eq, ha="left", va="center", fontsize=10.2 if i in (1, 3, 7) else 11)
        ax.plot([0.5, 8.0], [y0 - (i + 1) * row] * 2, lw=0.7, color="k")
    ax.plot([1.02, 1.02], [y0, y0 - 8 * row], lw=0.7, color="k")
    # symbol chart
    ctop = y0 - 8 * row - 0.25
    cols, nrow, cw, rh = 5, 7, 7.7 / 5, 0.52
    h_all = 0.5 + nrow * rh
    ax.add_patch(Rectangle((0.4, ctop - h_all), 7.7, h_all, fill=False, lw=0.9))
    ax.text(4.25, ctop - 0.25, "THE OMNI-COMPASS SYMBOL CHART", ha="center", va="center", fontsize=13.5, fontweight="bold")
    g0 = ctop - 0.5
    for r in range(nrow + 1):
        ax.plot([0.4, 8.1], [g0 - r * rh] * 2, lw=0.7, color="k")
    for c in range(1, cols):
        ax.plot([0.4 + c * cw] * 2, [g0, g0 - nrow * rh], lw=0.7, color="k")
    for k, (sym, desc) in enumerate(SYMS):
        r, c = divmod(k, cols); xc = 0.4 + (c + 0.5) * cw; yt = g0 - r * rh
        ax.text(xc, yt - 0.15, sym, ha="center", va="center", fontsize=12.5)
        ax.text(xc, yt - 0.37, desc, ha="center", va="center", fontsize=6.9, linespacing=1.0)
    ax.text(4.25, 0.55, "www.omni-compass.com", ha="center", va="center", fontsize=10.5, fontweight="bold")
    ax.text(4.25, 0.33, "U.S. PATENTS / COPYRIGHTS / TRADEMARKS — © ® 2026", ha="center", va="center", fontsize=8)
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"OMNI_COMPASS_PLATE.{ext}", dpi=200)
    print("written", OUT / "OMNI_COMPASS_PLATE.png", OUT / "OMNI_COMPASS_PLATE.pdf")


if __name__ == "__main__":
    build()
