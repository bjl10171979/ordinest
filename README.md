# Ordinest — compliance alerts, without the legalese

Ordinest watches official government sources for short-term-rental rule
changes and sends subscribers plain-English alerts with links to the
original. This repo is the whole machine: the monitor, the site, and the
daily scheduled check — built to run at **$0/month**.

## What's here

```
ordinest/
├── monitor.py            # the watcher — Python stdlib, no pip installs
├── sources.json          # which official pages to watch (7 sources, 5 cities)
├── snapshots/            # last known clean copy of each page (committed)
├── alerts/               # DRAFT alerts land here when a page changes
├── ALERT_TEMPLATE.md     # the finished alert format + review checklist
├── .github/workflows/    # daily GitHub Action (runs free — public repo)
└── site/                 # the website (GitHub Pages — free)
    ├── index.html        #   landing page: how it works, cities, pricing
    ├── style.css
    └── cities/*.html     #   one SEO page per city, with real source links
```

## How the monitor works

1. Fetches each URL in `sources.json`.
2. Strips the page to readable text (nav, script, style removed).
3. Compares against the snapshot in `snapshots/`.
4. **Changed?** → writes a DRAFT to `alerts/` with a word-level diff and a
   human checklist, then rebaselines the snapshot.
5. **Fetch failed?** → reports it and touches nothing. A dead fetch never
   looks like a rule change.

Two fetch modes per source:

- default — direct HTTP fetch (Nashville, Denver, New Orleans, Tahoe).
- `"renderer": "chromium"` — the page is JS-rendered and behind Akamai
  bot protection (Palm Springs). The monitor renders it in headless
  Chromium with a normal browser User-Agent and reads the finished DOM.
  Uses any of `chromium`, `chromium-browser`, `google-chrome`,
  `google-chrome-stable` found on the machine.

### Run it by hand

```bash
python3 monitor.py
```

First run saves baselines. Later runs report `OK` / `CHANGED` / `FAIL`.
Drafts in `alerts/` are **never sent as-is** — they are review material.

## Going live (the free stack)

### 1. GitHub (free — do this first)

1. Create a free account at github.com (if Dad doesn't have one).
2. New **public** repository named `ordinest` — public = Actions free
   and unlimited.
3. From this folder:
   ```bash
   git init
   git add -A
   git commit -m "Ordinest: monitor + site + daily check"
   git remote add origin git@github.com:USERNAME/ordinest.git
   git push -u origin main
   ```
4. Actions tab → the workflow runs daily at 13:00 UTC (8 AM CDT) and on
   demand via **Run workflow**. Results appear in the run's job summary.

**First-run checks after pushing:**

- Do all 7 sources pass from GitHub's servers? (Akamai may treat those
  IPs differently than home — if Palm Springs fails there, the job summary
  shows it and we adjust.)
- Watch the first scheduled run before trusting it.

### 2. Email — Brevo (free tier)

- 300 emails/day, ~100,000 contacts stored, no credit card.
- Create account → Contacts → create list "Ordinest early access".
- Forms → create a signup form → paste the generated `<form>` into
  `site/index.html` (replaces the current `mailto:` button).
- Sending address: verify a domain you control, or start with Brevo's
  shared sender until a domain exists.

### 3. Publishing the site — GitHub Pages (free)

- Repo → Settings → Pages → Deploy from branch → `main` / `site` folder.
- Site appears at `https://USERNAME.github.io/ordinest/`.
- Optional custom domain later: ~$10–12/year (Cloudflare at-cost pricing).
  Until then the free `github.io` address is fine.

### 4. Payments — Stripe (only when the first subscriber says yes)

- No monthly fee — 2.9% + 30¢ per successful charge (US cards).
- Create account → Payment Links → one link per plan → drop the links
  into the pricing section when we're ready to charge.
- Stripe needs: legal name, EIN/SSN, bank account for payouts. Dad's
  accounts, Dad's name — nothing here can be set up by Piper.

## The honest operating loop

1. Daily: GitHub Action checks all sources (automatic, free).
2. If something changed: a draft appears in `alerts/` (and in the job
   summary).
3. **Human review session (Piper + Dad):** open the official source link,
   confirm it's real, write the plain-English alert using
   `ALERT_TEMPLATE.md`, then send via Brevo.
4. Nothing goes out without its official source link and the
   informational disclaimer. Not legal advice — never will be.

## Known limits (on purpose)

- **No auto-send.** A machine found the change; a person approves the
  words. Accuracy is the whole business.
- **Daily, not minute-by-minute.** 24-hour detection is plenty for
  regulation — cities give weeks/months of effective dates.
- **Pages we can't read, we report as FAIL** — we never pretend a broken
  fetch is a clean page.
- **Revenue starts at $0.** SEO city pages take 3–9 months to rank. The
  first money comes from early-access hosts we onboard personally.
