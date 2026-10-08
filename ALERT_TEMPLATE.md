# Ordinest alert format

This is what a finished alert looks like. The monitor's draft in `alerts/`
gives you the *what changed* part (the diff) — you turn it into this.

Rules that never bend:

1. **Every alert links the official page it came from.** No source, no send.
2. **Plain English.** No legalese. If a host can't understand it in one
   read, rewrite it.
3. **Say what to DO, not just what changed.**
4. **Effective dates in bold.** Deadlines are the whole point.
5. **Informational — not legal advice** stays in the footer, every time.
6. **A human approved it.** Drafts from the monitor are never sent as-is.

---

## Subject line

```
[City] short-term rental rule changed: <the thing> (effective <date>)
```

Examples:

- `Palm Springs: new ordinance caps contracts at 26/year (effective Jan 1)`
- `South Lake Tahoe: new VHR applications now go to a waitlist`
- `Nashville: permit applications moved to a new online system`

## Body

```
Hi {{first_name}},

A rule changed for short-term rentals in {{city}}.

WHAT CHANGED
{{One or two sentences, plain English. What the rule is now.}}

WHEN IT TAKES EFFECT
**{{effective date, or "already in effect"}}**

WHAT TO DO
- {{Actionable step 1 — e.g. "Renew by X date"}}
- {{Actionable step 2 — e.g. "Update your listing to show the permit number"}}
- {{Or "Nothing right now — we'll alert you if your permit is affected"}}

OFFICIAL SOURCE
{{url — the exact city page this came from}}

Questions? Just reply to this email.

— Ordinest
Compliance, without the legalese.

---
Informational only — not legal advice. Rules change and pages can be
updated after we check them. Always confirm with your city before acting.
Unsubscribe: {{unsubscribe_url}}
```

## Review checklist (copy into each draft)

- [ ] Opened the official URL — change is real, not a site redesign/banner
- [ ] Summary is plain English and says what to DO
- [ ] Effective date verified on the official page
- [ ] Source link present and working
- [ ] Disclaimer footer intact
- [ ] Approved by a human (Piper + Dad) — monitor drafts never auto-send
