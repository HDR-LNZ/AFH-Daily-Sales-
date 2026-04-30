#!/usr/bin/env python3
"""Refresh the WEBSITE_DOCTORS map in index.html from healthhubalfuttaim.com.

Run this whenever the website roster changes (new hires, departures, slug renames):

    python3 scripts/update-doctor-map.py

It fetches the doctor sitemap, pulls each profile page's <h1>, and rewrites the
WEBSITE_DOCTORS block in-place. New doctors with reasonable name overlap will
match automatically via the runtime fuzzy matcher in getDoctorProfileUrl.
"""
from __future__ import annotations
import re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = __import__('pathlib').Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
SITEMAP = "https://www.healthhubalfuttaim.com/doctor-sitemap.xml"
UA = {"User-Agent": "Mozilla/5.0"}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="ignore")


def main() -> int:
    print(f"[1/3] Fetching sitemap: {SITEMAP}")
    sm = fetch(SITEMAP)
    slugs = sorted(set(re.findall(r"doctor/([a-z0-9-]+)/", sm)))
    print(f"      → {len(slugs)} doctor slugs")

    print(f"[2/3] Fetching {len(slugs)} profile pages (parallel)…")

    def get_h1(slug: str) -> tuple[str, str]:
        try:
            html = fetch(f"https://www.healthhubalfuttaim.com/doctor/{slug}/")
            m = re.search(r"<h1[^>]*>([^<]+)<", html)
            return slug, (m.group(1).strip() if m else "")
        except Exception as e:
            return slug, f"ERROR:{type(e).__name__}"

    with ThreadPoolExecutor(max_workers=25) as ex:
        results = dict(ex.map(get_h1, slugs))

    bad = [s for s, n in results.items() if not n or n.startswith("ERROR")]
    if bad:
        print(f"      ! {len(bad)} pages had no usable H1: {bad[:5]}{'…' if len(bad)>5 else ''}")
    good = {s: n for s, n in results.items() if n and not n.startswith("ERROR")}
    print(f"      → {len(good)} usable entries")

    print(f"[3/3] Rewriting WEBSITE_DOCTORS in {INDEX.name}")
    body = ",".join(
        f'"{s}":"{n.replace(chr(34), chr(92)+chr(34))}"' for s, n in sorted(good.items())
    )
    today = __import__('datetime').date.today().isoformat()
    new_block = (
        "// Live website doctor map (slug → H1 name on healthhubalfuttaim.com).\n"
        "// Refresh via: python3 scripts/update-doctor-map.py (re-fetches sitemap, updates this block).\n"
        f"// Last updated: {today} — {len(good)} doctors.\n"
        f"const WEBSITE_DOCTORS = {{{body}}};\n"
        "const ACTIVE_DOCTOR_SLUGS = new Set(Object.keys(WEBSITE_DOCTORS));"
    )

    src = INDEX.read_text()
    pattern = (
        r"// Live website doctor map.*?\n"
        r"const ACTIVE_DOCTOR_SLUGS = new Set\(Object\.keys\(WEBSITE_DOCTORS\)\);"
    )
    new_src, n = re.subn(pattern, new_block, src, count=1, flags=re.DOTALL)
    if n != 1:
        print("ERROR: could not locate WEBSITE_DOCTORS block in index.html", file=sys.stderr)
        return 1
    INDEX.write_text(new_src)
    print(f"      ✓ wrote {len(good)} doctors")
    print("\nDone. Review the diff and commit:")
    print("  git diff index.html | head -40")
    print("  git add index.html && git commit -m 'Refresh WEBSITE_DOCTORS map'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
