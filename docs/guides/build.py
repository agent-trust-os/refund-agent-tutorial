"""Build the guide pages: ``python docs/guides/build.py`` writes harness.html (and any other *.src.html) by
inlining style.css, the code snippets (docs/guides/snippets) and the captured outputs (docs/guides/outputs).

``--check`` rebuilds in memory and fails if a page on disk differs, so a page cannot drift from the code.
Placeholders: ``{{css}}``, ``{{snippet:NAME}}``, ``{{out:NAME}}``, ``{{file:PATH}}`` (a repo file, as is), ``{{sol:PATH}}`` (a file as on the solution branch).
"""
from __future__ import annotations

import difflib
import html
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def snippet(name: str) -> str:
    lines = (HERE / "snippets" / f"{name}.txt").read_text().splitlines()
    target = next(line.split(": ", 1)[1] for line in lines if line.startswith("# target: "))
    body = [line for line in lines if not re.match(r"# (target|marker|replaces): ", line)]
    return f'<div class="path">{html.escape(target)}</div><pre><code>{html.escape(chr(10).join(body))}</code></pre>'


def repo_file(path: str) -> str:
    text = (HERE.parent.parent / path).read_text().rstrip()
    return f'<div class="path">{html.escape(path)}</div><pre><code>{html.escape(text)}</code></pre>'


BASELINES = ("feat/postgres-mailpit", "main")     # the template a reader clones; the first that exists is used


def _git_show(ref: str, path: str) -> str | None:
    result = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=HERE, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def _lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if "TODO(AgentTrust" not in line]


def solution_file(path: str) -> str:
    """A file as it is on the ``solution`` branch, in full. Lines that are not in the cloned template
    (what you add after cloning) are marked green."""
    final = _lines(_git_show("solution", path) or "")
    base = next((ref for ref in BASELINES if _git_show(ref, "python/pyproject.toml")), BASELINES[-1])
    before = _lines(_git_show(base, path) or "")
    added = set()
    for tag, _, _, j1, j2 in difflib.SequenceMatcher(None, before, final, autojunk=False).get_opcodes():
        if tag in ("insert", "replace"):
            added.update(range(j1, j2))
    rows = "".join(
        f'<span class="ln{" add" if i in added else ""}">{html.escape(line) or " "}</span>'
        for i, line in enumerate(final))
    note = ' <span class="legend">(green = lines you add)</span>' if added else ""
    return f'<div class="path">{html.escape(path)}{note}</div><pre><code>{rows}</code></pre>'


def output(name: str) -> str:
    return f"<pre><code>{html.escape((HERE / 'outputs' / f'{name}.txt').read_text().rstrip())}</code></pre>"


def render(source: Path) -> str:
    text = source.read_text()
    text = text.replace("{{css}}", (HERE / "style.css").read_text().strip())
    text = re.sub(r"\{\{snippet:([\w-]+)\}\}", lambda m: snippet(m.group(1)), text)
    text = re.sub(r"\{\{sol:([\w./-]+)\}\}", lambda m: solution_file(m.group(1)), text)
    text = re.sub(r"\{\{file:([\w./-]+)\}\}", lambda m: repo_file(m.group(1)), text)
    return re.sub(r"\{\{out:([\w-]+)\}\}", lambda m: output(m.group(1)), text)


def main() -> int:
    check = "--check" in sys.argv
    bad = 0
    for source in sorted(HERE.glob("*.src.html")):
        target = source.with_name(source.name.replace(".src.html", ".html"))
        built = render(source)
        if check:
            if not target.exists() or target.read_text() != built:
                print(f"{target.name} is out of date: run python docs/guides/build.py")
                bad = 1
        else:
            target.write_text(built)
            print("wrote", target.name)
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
