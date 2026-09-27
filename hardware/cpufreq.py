"""CPUFreq contract used by the Omni-Compass hardware ceiling muscle.

The schedutil *model* and the sysfs *actuator* are deliberately separate:

* ``schedutil_frequency_invariant()`` is the documented frequency-invariant CFS
  shape: min(1, 1.25*u), with the 0.8 tipping point.
* ``CpuFreqPolicies`` never reimplements schedutil.  It only constrains the
  kernel policy by writing ``scaling_max_freq`` and can restore the exact
  pre-Omni limits.

A real run must record the scaling driver/governor.  ``intel_pstate`` active
mode (including HWP) has different frequency-selection semantics; a ceiling
write can still be a real policy bound, but must not be reported as a
schedutil-equivalence experiment.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


SCHEDUTIL_TIPPING_CONSTANT = 1.25
SCHEDUTIL_TIPPING_UTIL = 1.0 / SCHEDUTIL_TIPPING_CONSTANT  # 0.8


def schedutil_frequency_invariant(util_fraction: float, f_min_fraction: float = 0.0) -> float:
    """Normalized frequency request for frequency-invariant CFS utilization.

    This intentionally models only the documented CFS proportional branch.
    OPP/driver resolution, uclamp, RT/DL max jumps, IO-wait boost, rate limiting,
    thermal constraints, PM QoS and hardware coordination are outside this
    scalar map and must be represented separately in evidence.
    """
    u = max(0.0, float(util_fraction))
    floor = max(0.0, min(1.0, float(f_min_fraction)))
    return min(1.0, max(floor, SCHEDUTIL_TIPPING_CONSTANT * u))


@dataclass(frozen=True)
class PolicySnapshot:
    policy: str
    path: str
    cpuinfo_min_freq: int
    cpuinfo_max_freq: int
    scaling_min_freq: int
    scaling_max_freq: int
    scaling_driver: str
    scaling_governor: str
    affected_cpus: str

    def as_dict(self) -> dict:
        return asdict(self)


class CpuFreqPolicies:
    """Discover, cap, and exactly restore Linux CPUFreq policy ceilings."""

    def __init__(self, root: str | Path = "/sys/devices/system/cpu/cpufreq"):
        self.root = Path(root)
        self._original: dict[str, PolicySnapshot] = {}

    @staticmethod
    def _read_text(path: Path, default: str = "") -> str:
        try:
            return path.read_text().strip()
        except OSError:
            return default

    @classmethod
    def _read_int(cls, path: Path, default: int = 0) -> int:
        try:
            return int(cls._read_text(path))
        except (TypeError, ValueError):
            return default

    def policy_dirs(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted((p for p in self.root.glob("policy*") if p.is_dir()), key=lambda p: p.name)

    def snapshot(self) -> list[PolicySnapshot]:
        rows: list[PolicySnapshot] = []
        for p in self.policy_dirs():
            s = PolicySnapshot(
                policy=p.name,
                path=str(p),
                cpuinfo_min_freq=self._read_int(p / "cpuinfo_min_freq"),
                cpuinfo_max_freq=self._read_int(p / "cpuinfo_max_freq"),
                scaling_min_freq=self._read_int(p / "scaling_min_freq"),
                scaling_max_freq=self._read_int(p / "scaling_max_freq"),
                scaling_driver=self._read_text(p / "scaling_driver", "unknown"),
                scaling_governor=self._read_text(p / "scaling_governor", "unknown"),
                affected_cpus=self._read_text(p / "affected_cpus", ""),
            )
            rows.append(s)
        return rows

    def capture_original(self) -> list[PolicySnapshot]:
        rows = self.snapshot()
        if not rows:
            raise RuntimeError(f"no CPUFreq policy directories found under {self.root}")
        if not self._original:
            self._original = {r.policy: r for r in rows}
        return rows

    def assert_schedutil(self) -> None:
        rows = self.capture_original()
        bad = [f"{r.policy}:{r.scaling_driver}/{r.scaling_governor}" for r in rows if r.scaling_governor != "schedutil"]
        if bad:
            raise RuntimeError("schedutil required for this evidence lane; found " + ", ".join(bad))

    def apply_cap(self, cap: float, dry_run: bool = False) -> list[dict]:
        """Set each scaling_max_freq to a fraction of its pre-Omni ceiling.

        The operation cannot raise a pre-existing ceiling.  The requested value
        is clamped at scaling_min_freq.  The kernel/driver may further resolve or
        constrain the effective operating point.
        """
        rows = self.capture_original()
        c = max(0.0, min(1.0, float(cap)))
        writes: list[dict] = []
        for now in rows:
            orig = self._original[now.policy]
            # Preserve the operator's pre-existing maximum even when it is below
            # the silicon-reported cpuinfo maximum.
            base = orig.scaling_max_freq or orig.cpuinfo_max_freq
            if orig.cpuinfo_max_freq:
                base = min(base, orig.cpuinfo_max_freq) if base else orig.cpuinfo_max_freq
            floor = max(0, now.scaling_min_freq)
            desired = max(floor, min(base, int(round(base * c))))
            target = Path(now.path) / "scaling_max_freq"
            rec = {
                "policy": now.policy,
                "path": str(target),
                "before_khz": now.scaling_max_freq,
                "original_khz": orig.scaling_max_freq,
                "requested_khz": desired,
                "cap": c,
                "driver": now.scaling_driver,
                "governor": now.scaling_governor,
                "dry_run": bool(dry_run),
            }
            writes.append(rec)
            if not dry_run:
                target.write_text(str(desired))
        return writes

    def restore(self, dry_run: bool = False) -> list[dict]:
        if not self._original:
            return []
        current = {r.policy: r for r in self.snapshot()}
        writes: list[dict] = []
        for policy, orig in sorted(self._original.items()):
            now = current.get(policy)
            target = Path(orig.path) / "scaling_max_freq"
            rec = {
                "policy": policy,
                "path": str(target),
                "before_khz": now.scaling_max_freq if now else None,
                "restore_khz": orig.scaling_max_freq,
                "driver": orig.scaling_driver,
                "governor": orig.scaling_governor,
                "dry_run": bool(dry_run),
            }
            writes.append(rec)
            if not dry_run:
                target.write_text(str(orig.scaling_max_freq))
        return writes

    @property
    def original(self) -> Iterable[PolicySnapshot]:
        return tuple(self._original[k] for k in sorted(self._original))
