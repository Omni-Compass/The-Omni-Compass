"""SHA-256 of a Python file's syntax tree with comments and docstrings removed."""
import ast, hashlib, sys


def strip_docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant) \
                    and isinstance(b[0].value.value, str):
                node.body = b[1:] or [ast.Pass()]
    return tree


def fingerprint(path):
    tree = strip_docstrings(ast.parse(open(path, encoding="utf-8").read()))
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(fingerprint(p), p)
