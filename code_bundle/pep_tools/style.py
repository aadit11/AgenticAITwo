"""Checks for the PEP 8 rule that imports usually occupy separate lines."""

import ast

STDLIB_MODULES = frozenset(
    {
        "os",
        "sys",
        "re",
        "json",
        "pathlib",
        "sqlite3",
        "typing",
        "dataclasses",
        "itertools",
        "collections",
    }
)


def import_statements(source: str) -> list[ast.Import | ast.ImportFrom]:
    """Return the import nodes in source, ignoring syntax errors by raising them."""
    tree = ast.parse(source)
    return [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]


def imports_are_on_separate_lines(source: str) -> bool:
    """PEP 8: imports should usually be on separate lines.

    `import os, sys` is the form the style guide marks as wrong.
    `from module import a, b` is allowed.
    """
    for node in import_statements(source):
        if isinstance(node, ast.Import) and len(node.names) > 1:
            return False
    return True


def import_group(module: str) -> str:
    """Label a top-level module as stdlib or other. Local packages are 'other'."""
    root = module.split(".", 1)[0]
    if root in STDLIB_MODULES:
        return "stdlib"
    return "other"
