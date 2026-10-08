#!/usr/bin/env python3
"""
Ordinest source monitor
=======================
Watches official government pages for short-term-rental rule changes.

How it works:
  1. Fetch each URL in sources.json (stdlib only, no pip installs).
  2. Strip the page down to readable text (nav/script noise removed).
  3. Compare against the last clean snapshot in snapshots/.
  4. If it changed -> write a DRAFT alert into alerts/ for human review,
     then update the snapshot so tomorrow starts from a clean baseline.
  5. If a fetch fails (timeout, 404, blocked) -> report it, change NOTHING.
     A dead fetch must never look like a rule change.

Exit codes:
  0 = everything checked (even if changes were found)
  1 = sources.json missing/unreadable, or a fatal error
"""

import difflib
import html
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
SNAP_DIR = ROOT / "snapshots"
ALERT_DIR = ROOT / "alerts"
SOURCES_FILE = ROOT / "sources.json"

USER_AGENT = (
    "OrdinestMonitor/1.0 (compliance watch; +https://ordinest.pages.dev)"
)
TIMEOUT_SECONDS = 45
# Anything smaller than this after cleaning is almost certainly an error
# page or a block page, not real content. Never overwrite a snapshot with it.
MIN_CONTENT_CHARS = 200
# How many words of context to show around each changed region.
DIFF_CONTEXT_WORDS = 30


class TextExtractor(HTMLParser):
    """Pulls visible text out of HTML, skipping script/style/head noise."""

    SKIP_TAGS = {"script", "style", "noscript", "svg", "head", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            self.chunks.append(data)


def extract_text(raw_html: str) -> str:
    parser = TextExtractor()
    parser.feed(raw_html)
    text = " ".join(parser.chunks)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch(url: str) -> str:
    """Fetch a page and return cleaned text. Raises on any problem."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        status = getattr(resp, "status", 200)
        if status != 200:
            raise HTTPError(url, status, f"HTTP {status}", {}, None)
        body = resp.read()
    # Most .gov pages are UTF-8; fall back gracefully.
    try:
        raw_html = body.decode("utf-8")
    except UnicodeDecodeError:
        raw_html = body.decode("latin-1", errors="replace")
    return extract_text(raw_html)


# --- JS-rendered sources ---------------------------------------------------
# Some city sites (e.g. Palm Springs) serve only a JavaScript shell to
# scripts and block headless-chrome user agents at Akamai's edge. For those,
# we render the page in a real browser binary with a normal browser
# User-Agent and read the finished DOM. Works locally and on GitHub runners
# (which ship Chrome under one of these names).
RENDERER_BROWSERS = (
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
)
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
)
RENDER_BUDGET_MS = 25000  # how long to let the page's JS run


def find_browser() -> str | None:
    for name in RENDERER_BROWSERS:
        path = shutil.which(name)
        if path:
            return path
    return None


def fetch_rendered(url: str) -> str:
    """Render a JS-heavy page in headless Chromium and return its text."""
    browser = find_browser()
    if not browser:
        raise RuntimeError(
            "source needs a browser renderer but chromium/chrome is not installed"
        )
    cmd = [
        browser,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        f"--user-agent={BROWSER_UA}",
        f"--virtual-time-budget={RENDER_BUDGET_MS}",
        "--dump-dom",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=120)
    dom = proc.stdout.decode("utf-8", errors="replace")
    # Akamai's denial page is small and obvious - never snapshot it.
    if len(dom) < 5000 and "Access Denied" in dom:
        raise RuntimeError("blocked by CDN (Access Denied page)")
    if len(dom) < MIN_CONTENT_CHARS:
        raise RuntimeError(f"renderer returned only {len(dom)} chars")
    return extract_text(dom)


def word_changes(old: str, new: str, context: int = DIFF_CONTEXT_WORDS) -> list[str]:
    """Word-level diff rendered as readable context blocks."""
    a, b = old.split(), new.split()
    sm = difflib.SequenceMatcher(None, a, b)
    blocks: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        lo = max(0, min(i1, j1) - context)
        # Show surrounding words from the OLD text for orientation.
        hi = min(len(a), max(i2, j2) + context)
        before = " ".join(a[lo:i1])
        removed = " ".join(a[i1:i2])
        added = " ".join(b[j1:j2])
        after = " ".join(a[i2:hi])
        parts = []
        if before:
            parts.append(f"… {before}")
        if removed:
            parts.append(f"**- {removed}**")
        if added:
            parts.append(f"**+ {added}**")
        if after:
            parts.append(f"{after} …")
        blocks.append(" ".join(parts))
    return blocks


def slug_time() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def write_draft_alert(source: dict, old: str, new: str, when: str) -> Path:
    blocks = word_changes(old, new)
    diff_body = "\n\n".join(f"> {b}" for b in blocks) if blocks else (
        "> (text changed but no word-level differences were isolated)"
    )
    content = f"""---
status: needs-review
source_id: {source["id"]}
city: {source["city"]}
url: {source["url"]}
checked_utc: {when}
---

# DRAFT ALERT - {source["city"]} - {when[:10]}

**Watched page:** {source["label"]}
**URL:** {source["url"]}
**Detected (UTC):** {when}

## What appears to have changed

{diff_body}

## Before this goes anywhere

- [ ] Open the official URL above and confirm the change is real
      (ignore cosmetic site redesigns, banners, calendars).
- [ ] Write the plain-English summary using ALERT_TEMPLATE.md.
- [ ] Note any effective dates or deadlines stated on the official page.
- [ ] Keep the source link in the alert. Always.
- [ ] Second pair of eyes (Piper + Dad) before send.

*This file was drafted automatically by the Ordinest monitor and is NOT
finished content. Nothing is sent to subscribers until a human approves it.*

*Informational only - not legal advice.*
"""
    path = ALERT_DIR / f"{source['id']}-{slug_time()}.md"
    path.write_text(content, encoding="utf-8")
    return path


def main() -> int:
    if not SOURCES_FILE.exists():
        print(f"FATAL: {SOURCES_FILE} not found.", file=sys.stderr)
        return 1

    try:
        data = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
        sources = data["sources"]
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"FATAL: cannot read sources.json: {exc}", file=sys.stderr)
        return 1

    SNAP_DIR.mkdir(exist_ok=True)
    ALERT_DIR.mkdir(exist_ok=True)

    when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ok = unchanged = changed = failed = 0
    summary_lines: list[str] = []

    for source in sources:
        sid = source["id"]
        snap_path = SNAP_DIR / f"{sid}.txt"
        label = f"{source['city']} ({sid})"

        renderer = source.get("renderer")
        try:
            if renderer == "chromium":
                new_text = fetch_rendered(source["url"])
            else:
                new_text = fetch(source["url"])
        except (
            URLError,
            HTTPError,
            TimeoutError,
            OSError,
            RuntimeError,
            subprocess.TimeoutExpired,
        ) as exc:
            failed += 1
            reason = getattr(exc, "reason", exc)
            summary_lines.append(f"- FAILED {label}: {reason}")
            print(f"[FAIL] {label}: {reason}")
            continue  # A dead fetch is never a change. Snapshots untouched.

        if len(new_text) < MIN_CONTENT_CHARS:
            failed += 1
            summary_lines.append(
                f"- SUSPECT {label}: only {len(new_text)} chars after cleaning "
                f"(error/block page?). Snapshot left untouched."
            )
            print(f"[SUSPECT] {label}: content too small ({len(new_text)} chars)")
            continue

        if not snap_path.exists():
            snap_path.write_text(new_text, encoding="utf-8")
            ok += 1
            summary_lines.append(f"- BASELINE {label}: first snapshot saved.")
            print(f"[BASELINE] {label}")
            continue

        old_text = snap_path.read_text(encoding="utf-8")
        if old_text == new_text:
            unchanged += 1
            summary_lines.append(f"- OK {label}: no change.")
            print(f"[OK] {label}: no change")
            continue

        # Something really changed - draft it for review, then rebaseline.
        alert_path = write_draft_alert(source, old_text, new_text, when)
        snap_path.write_text(new_text, encoding="utf-8")
        changed += 1
        summary_lines.append(
            f"- CHANGED {label}: draft written to alerts/{alert_path.name}"
        )
        print(f"[CHANGED] {label} -> {alert_path.name}")

    header = f"## Ordinest monitor - {when}\n\n"
    header += (
        f"Checked: {len(sources)} | unchanged: {unchanged} | "
        f"changed: {changed} | baselines: {ok} | failed: {failed}\n\n"
    )
    report = header + "\n".join(summary_lines) + "\n"
    print()
    print(report)

    # A partial outage is worth surfacing but should not fail the whole run:
    # the sites we DID read still get compared and drafted.
    return 0


if __name__ == "__main__":
    sys.exit(main())
