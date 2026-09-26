"""omnicompass/stack_sim.py blocks vs reference engine source."""
import ast, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def main():
    ref = (ROOT / "reference" / "omni_compass_reference_engine.py").read_text()
    t = ast.parse(ref); top = {}
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)): top[n.name] = n
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            for g in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                if isinstance(g, ast.Name): top[g.id] = n
    sim = (ROOT / "omnicompass" / "stack_sim.py").read_text()
    blocks = re.findall(r"# --- source line (\d+): (\S+)\n(.*?)(?=\n# --- source line |\Z)", sim, re.S)
    for line, name, body in blocks:
        n = top[name]; seg = ast.get_source_segment(ref, n)
        if getattr(n, "decorator_list", None):
            seg = "\n".join("@" + ast.get_source_segment(ref, d) for d in n.decorator_list) + "\n" + seg
        assert int(line) == n.lineno and body.strip() == seg.strip(), name
    print(f"stack_sim provenance: {len(blocks)}/{len(blocks)} blocks byte-identical to reference engine")
    print("PASS test_stack_sim_provenance")

if __name__ == "__main__":
    main()
