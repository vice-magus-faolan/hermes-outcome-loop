#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Conservative AST branch audit for the Phase-0 harness (not a full linter)."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def score(node):
    """Count branches including comprehensions; omit nested function bodies."""
    count = 0
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler)):
            count += 1
        if isinstance(child, ast.BoolOp):
            count += len(child.values) - 1
        if isinstance(child, ast.comprehension):
            count += 1 + len(child.ifs)
        count += score(child)
    return count


def results():
    """Return portable path/function scores for scripts and the fixture."""
    paths = sorted((ROOT / "scripts").glob("phase0_*.py")) + [ROOT / "tests/fixtures/phase0_plugin/__init__.py"]
    return [(str(path.relative_to(ROOT)), node.name, 1 + score(node))
            for path in paths for node in ast.walk(ast.parse(path.read_text()))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def main():
    records = results()
    for path, name, value in records:
        if value > 10:
            print(f"warning: {path}:{name} conservative complexity={value}")
    maximum = max(value for _, _, value in records)
    print(f"Audited {len(records)} functions; maximum conservative complexity={maximum}")
    return int(maximum > 15)


if __name__ == "__main__":
    raise SystemExit(main())
