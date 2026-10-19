#!/usr/bin/env python3
"""Validate the skill's docs: file references, section refs and anchors.

    ./scripts/check-docs.py          # from the skill root, or anywhere

Catches the drift that plain proofreading misses:
  - `references/foo.md`, `scripts/bar.py`, `templates/baz.py` that don't exist
  - markdown links to missing files
  - `file.md §7` where that file has no section 7
  - `file.md#anchor` that matches no heading
  - bare `§7` inside a file with no section 7
  - SKILL.md frontmatter and reference-map coverage

Exit code 0 = clean, 1 = errors. Run it before every commit (CI does too).
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {".git", "scripts/__pycache__", "templates/__pycache__"}

errors = []
warnings = []


def err(where, msg):
    errors.append("%s: %s" % (where, msg))


def warn(where, msg):
    warnings.append("%s: %s" % (where, msg))


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        return fh.read()


def md_files():
    out = ["SKILL.md", "README.md"]
    for d in ("references", "templates"):
        full = os.path.join(ROOT, d)
        if os.path.isdir(full):
            for name in sorted(os.listdir(full)):
                if name.endswith(".md"):
                    out.append(d + "/" + name)
    return [p for p in out if os.path.isfile(os.path.join(ROOT, p))]


def headings(text):
    """[(level, text)] for ATX headings outside code fences."""
    out, fence = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if m:
            out.append((len(m.group(1)), m.group(2)))
    return out


def slug(title):
    """GitHub-style heading anchor: lowercase, strip punctuation, spaces -> '-'."""
    s = title.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def strip_code(text):
    """Drop fenced blocks and inline code, so prose checks ignore examples."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`[^`\n]+`", "", text)
    return text


def main():
    files = md_files()
    cache = {p: read(p) for p in files}
    heads = {p: headings(t) for p, t in cache.items()}
    slugs = {p: {slug(h) for _l, h in hs} for p, hs in heads.items()}

    # ---- frontmatter + map coverage -------------------------------------
    skill = cache.get("SKILL.md", "")
    if not skill.startswith("---"):
        err("SKILL.md", "missing YAML frontmatter")
    else:
        fm = skill.split("---", 2)[1]
        if "name: m10-dev" not in fm:
            err("SKILL.md", "frontmatter name is not m10-dev")
        if "description:" not in fm:
            err("SKILL.md", "frontmatter has no description")
    for p in files:
        if p.startswith("references/") and p not in skill:
            warn(p, "not mentioned in SKILL.md reference map")

    # ---- file references -------------------------------------------------
    path_re = re.compile(r"(?<![\w/])((?:references|scripts|templates)/[A-Za-z0-9_.\-/]+)")
    for p in files:
        for m in path_re.finditer(cache[p]):
            target = m.group(1).rstrip(".,;:)")
            if not os.path.exists(os.path.join(ROOT, target)):
                err(p, "missing file: " + target)

    # ---- markdown links --------------------------------------------------
    link_re = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
    for p in files:
        for m in link_re.finditer(cache[p]):
            target = m.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path, _, anchor = target.partition("#")
            full = p if not path else os.path.normpath(
                os.path.join(os.path.dirname(p), path))
            if not os.path.exists(os.path.join(ROOT, full)):
                err(p, "broken link: " + target)
            elif anchor and full.endswith(".md") and anchor not in slugs.get(full, set()):
                err(p, "no heading for anchor #%s in %s" % (anchor, full))

    # ---- section refs: file.md §N / §N.M ---------------------------------
    ref_re = re.compile(
        r"((?:references/)?[A-Za-z0-9_.\-]+\.md)`?\s*§\s*(\d+(?:\.\d+)?)")
    seen = set()
    for p in files:
        for m in ref_re.finditer(cache[p]):
            target, num = m.group(1), m.group(2)
            if target not in cache:
                candidates = [
                    os.path.normpath(os.path.join(os.path.dirname(p), target)),
                    os.path.normpath(os.path.join("references", target)),
                    os.path.normpath(target),
                ]
                tpath = next((c for c in candidates if c in cache), None)
                if tpath is None:
                    err(p, "section ref to unknown file: " + target)
                    continue
                target = tpath
            key = (target, num)
            if key in seen:
                continue
            seen.add(key)
            if not has_section(heads[target], num):
                err(p, "%s has no section %s" % (target, num))

    # ---- bare section refs (same file) -----------------------------------
    bare_re = re.compile(r"§\s*(\d+(?:\.\d+)?)")
    for p in files:
        body = cache[p]
        # remove the file-qualified ones so they are not counted twice
        body_wo = ref_re.sub("", body)
        for m in bare_re.finditer(body_wo):
            num = m.group(1)
            if not has_section(heads[p], num):
                err(p, "no section %s in this file" % num)

    for line in warnings:
        print("WARN", line)
    for line in errors:
        print("ERR ", line)
    print("\n%d files checked, %d errors, %d warnings" %
          (len(files), len(errors), len(warnings)))
    return 1 if errors else 0


def has_section(heads, num):
    for _level, title in heads:
        m = re.match(r"^(\d+(?:\.\d+)?)\.?\s", title)
        if m and m.group(1) == num:
            return True
    return False


if __name__ == "__main__":
    sys.exit(main())
