"""Apply the snippets in docs/guides/snippets to the repo, in file-name order: each replaces its
``TODO(AgentTrust n/11)`` marker line (and ``replaces: k`` lines after it), keeping the marker's indentation.

    python docs/guides/apply_snippets.py [--only 1-7] [--root .]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

HERE = Path(__file__).parent


def parse(path: Path) -> tuple[dict[str, str], list[str]]:
    header, body = {}, []
    for line in path.read_text().splitlines():
        match = re.match(r"# (target|marker|replaces): (.*)", line) if not body else None
        if match:
            header[match.group(1)] = match.group(2)
        else:
            body.append(line)
    return header, body


def apply(root: Path, first: int = 1, last: int = 99) -> list[str]:
    done = []
    for path in sorted((HERE / "snippets").glob("*.txt")):
        header, body = parse(path)
        n = int(header["marker"])
        if not first <= n <= last:
            continue
        target = root / header["target"]
        lines = target.read_text().split("\n")
        index = next(i for i, line in enumerate(lines) if f"TODO(AgentTrust {n}/11)" in line)
        indent = re.match(r"\s*", lines[index]).group(0)
        new = [indent + line if line else line for line in body]
        lines[index:index + 1 + int(header.get("replaces", 0))] = new
        target.write_text("\n".join(lines))
        done.append(path.name)
    return done


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="1-99", help="marker range, for example 1-7")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    low, _, high = args.only.partition("-")
    for name in apply(Path(args.root), int(low), int(high or low)):
        print("applied", name)
