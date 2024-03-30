import ast
import subprocess
import sys
from argparse import ArgumentParser
from ast import Import, ImportFrom, alias
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def _generate(start: Path, exclude: Iterable[Path], out_dir: Path, name: str) -> None:
    dot = _generate_dot(start=start, exclude=exclude, name=name)
    dot_file = out_dir.joinpath(f"{name}.dot")
    dot_file.write_text(dot)
    svg = out_dir.joinpath(f"{name}.svg")
    subprocess.run(["dot", dot_file.as_posix(), "-T", "svg", "-o", svg.as_posix()])


def _check(start: Path, exclude: Iterable[Path], out_dir: Path, name: str) -> None:
    dot = _generate_dot(start=start, exclude=exclude, name=name)
    dot_file = out_dir.joinpath(f"{name}.dot")
    if not dot_file.is_file():
        print("There is no existing dependency graph.")
        sys.exit(1)
    if dot_file.read_text() != dot:
        print("There are changes to the dependency graph!")
        sys.exit(1)
    print("The dependency graph is up to date.")
    sys.exit(0)


def _generate_dot(start: Path, exclude: Iterable[Path], name: str) -> str:
    files = _find_files(start=start, exclude=exclude)
    deps_by_file = {f: _find_imports(f, start) for f in files}
    dependency_graph: Dict[str, Set[str]] = {}
    for f, deps in deps_by_file.items():
        package = _get_package_name(f, start)
        if package == ".":
            continue
        deps = {_get_package_name(d, start) for d in deps}
        # Ignore dependencies within a package
        deps = {d for d in deps if d != package}
        dependency_graph[package] = dependency_graph.get(package, set()).union(deps)
    dot = _convert_to_dot(dependency_graph)
    return dot


def _find_files(start: Path, exclude: Iterable[Path]) -> Iterable[Path]:
    return {
        f for f in start.rglob("*.py") if all(not f.is_relative_to(e) for e in exclude)
    }


def _find_imports(f: Path, start: Path) -> Set[Path]:
    a = ast.parse(source=f.read_text(), filename=f)
    targets: Set[Path] = set()
    for s in a.body:
        if isinstance(s, Import):
            for a in s.names:
                p = _resolve_import(a, start)
                if p is not None:
                    targets.add(p)
        elif isinstance(s, ImportFrom):
            for a in s.names:
                p = _resolve_import_from(a, s.module, s.level, f, start)
                if p is not None:
                    targets.add(p)
    return targets


def _resolve_import(a: alias, start: Path) -> Optional[Path]:
    p = start.joinpath(*a.name.split("."))
    if p.exists():
        return p
    if p.with_suffix(".py").exists():
        return p.with_suffix(".py")
    return None


def _resolve_import_from(
    a: alias, module: Optional[str], level: int, f: Path, start: Path
) -> Optional[Path]:
    base = start if level == 0 else _get_parent(f, level)
    mod = module or ""
    p = base.joinpath(*mod.split("."), a.name)
    if p.exists():
        return p
    if p.with_suffix(".py").exists():
        return p.with_suffix(".py")
    if p.parent.exists():
        return p.parent
    if p.parent.with_suffix(".py").exists():
        return p.parent.with_suffix(".py")
    return None


def _get_parent(p: Path, n: int) -> Path:
    for _ in range(n):
        p = p.parent
    return p


def _get_package_name(f: Path, start: Path) -> str:
    return (
        start.relative_to(start)
        if f.parent == start and f.is_file()
        else (
            f.relative_to(start)
            if f.parent == start
            else f.relative_to(start).parents[-2]
        )
    ).as_posix()


def _convert_to_dot(dependency_graph: Dict[str, Set[str]]) -> str:
    packages = sorted(dependency_graph.keys())
    lines: List[str] = []
    for p in packages:
        lines.append(f'"{p}" [shape="rect"];')
        deps = [f'"{d}"' for d in sorted(dependency_graph[p])]
        lines.append(f'"{p}" -> {{{", ".join(deps)}}};')
    lines = [f"    {line}" for line in lines]
    joined_lines = "\n".join(lines)
    return f"digraph G {{\n{joined_lines}\n}}"


if __name__ == "__main__":
    parser = ArgumentParser(
        prog="dependoc",
        description="generate a block diagram showing dependencies between packages",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    generate_parser = subparsers.add_parser(
        "generate",
        help="generate an image of the dependency graph",
    )
    check_parser = subparsers.add_parser(
        "check",
        help="check that the existing dependency graph is up to date",
    )
    args = parser.parse_args()
    start_dir = SCRIPTS_DIR
    exclude = [SCRIPTS_DIR.joinpath(".venv"), SCRIPTS_DIR.joinpath("test")]
    out_dir = Path(__file__).parent
    name = "dependencies"
    if args.subcommand == "generate":
        _generate(start=start_dir, exclude=exclude, out_dir=out_dir, name=name)
    elif args.subcommand == "check":
        _check(start=start_dir, exclude=exclude, out_dir=out_dir, name=name)
    elif args.subcommand is None:
        parser.print_usage()
    else:
        parser.error(f"unrecognized subcommand '{args.subcommand}'")
