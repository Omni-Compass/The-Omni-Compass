"""Remove comments and docstrings from a Python file; assert the program is unchanged."""
import ast, io, sys, tokenize
sys.path.insert(0, __import__("os").path.dirname(__file__))
from code_fingerprint import fingerprint


def strip(src):
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    edits = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant) \
                    and isinstance(b[0].value.value, str):
                d = b[0]
                edits.append((d.lineno, d.end_lineno, d.col_offset, len(b) == 1))
    for start, end, col, only in sorted(edits, reverse=True):
        repl = [" " * col + "pass\n"] if only else []
        lines[start - 1:end] = repl
    src = "".join(lines)
    toks = [t for t in tokenize.generate_tokens(io.StringIO(src).readline) if t.type != tokenize.COMMENT]
    return tokenize.untokenize(toks)


if __name__ == "__main__":
    src_path, dst_path = sys.argv[1], sys.argv[2]
    open(dst_path, "w", encoding="utf-8").write(strip(open(src_path, encoding="utf-8").read()))
    a, b = fingerprint(src_path), fingerprint(dst_path)
    print("program fingerprint original:", a)
    print("program fingerprint stripped:", b)
    assert a == b, "stripped file is not the same program"
    print("IDENTICAL PROGRAM")
