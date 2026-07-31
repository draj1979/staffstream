# LawGIQ Design System

LawGIQ is an AI-powered platform built to be a **comprehensive legal assistant for lawyers and law firms** — automating the repetitive parts of documentation and legal research so attorneys can focus on judgment.

This design system holds the brand foundations (color, type, motion, voice), reusable visual assets, and high-fidelity UI kits for both the **product workspace** and the **marketing website**.

---

## Index

| File / Folder | What's in it |
|---|---|
| `colors_and_type.css` | All tokens — palette, type, spacing, radii, shadows, motion — as CSS variables and semantic classes. The single source of truth. |
| `assets/` | Logos (mark, wordmark, inverse), brand glyph (§), hero background. Drop these into any LawGIQ surface. |
| `fonts/` | Notes on the type stack — fonts load from Google Fonts via `@import` in `colors_and_type.css`. |
| `preview/` | Design-system specimen cards. These power the Design System tab. |
| `ui_kits/web_app/` | The product surface — research workspace with sidebar, chat, source panel, citations, drafting view. Open `index.html`. |
| `ui_kits/marketing_site/` | Public marketing homepage. Open `index.html`. |
| `SKILL.md` | Agent-skill entry point for Claude Code / portable use. |

---

## Source materials

**None were attached.** The user provided:
- Company description: *"LawGIQ — AI-powered platform designed to be a comprehensive legal assistant for lawyers and law firms."*
- Palette reference: <https://colorhunt.co/palette/f5f5f576abae303841ff5722>

Everything else — logo, voice, layout patterns, UI screens — was designed from scratch in line with that brief. If the user has a real codebase, Figma file, or existing marketing site, those should be imported and the system reconciled against them.

---

## Brand thesis

LawGIQ sits at the intersection of **editorial authority** (the legal tradition: print, paper, precedent) and **considered AI tooling** (precise, never flashy). The product earns trust by looking like it was built by lawyers, not for them.

Three operating principles:

1. **Sober base, single accent.** Slate ink on bone paper. Teal as a calm advisory voice. Ember used surgically — a status flag, a primary CTA, never a gradient.
2. **Editorial typography.** Instrument Serif for display moments brings the gravitas of a legal periodical; Geist handles the working UI without any "startup" connotation.
3. **Precision over delight.** Animations are short, easing is gentle, hover states are *legible* not *playful*. No bounce. No confetti. The product respects the reader's time.

---

## Palette

| Token | Hex | Use |
|---|---|---|
| `--bone`   | `#F5F5F5` | Page background, paper-feel surface |
| `--teal`   | `#76ABAE` | Secondary brand — advisory, informational |
| `--slate`  | `#303841` | Primary ink, headers, chrome |
| `--ember`  | `#FF5722` | Single accent — primary CTAs, alerts, brand highlights |

Plus full derived scales for each (`--slate-50` … `--slate-950`, etc) — see `colors_and_type.css`.

---

## Type

| Role | Family | Notes |
|---|---|---|
| Display | **Instrument Serif** | Editorial, italic-friendly. Hero copy, marketing display. |
| UI / body | **Geist** | Neutral grotesk, excellent at small sizes, good for dense product UI. |
| Mono | **JetBrains Mono** | Citations, case numbers, code-like tokens. |

> **Substitution flag:** No custom font files were provided. All three are loaded from Google Fonts. **If LawGIQ has licensed fonts (e.g. a custom serif or commercial sans), drop the `.woff2` files into `fonts/` and update `colors_and_type.css`.**

---

## Content fundamentals

LawGIQ's voice is **counsel, not pep talk.** Imagine a senior associate explaining a tool to a partner — clear, brief, professional, never breezy.

**Tone & casing**
- Sentence case for everything except proper nouns — UI labels, buttons, headlines. ("Draft a memo" not "Draft A Memo".)
- Title case only on legal document titles inside content (e.g. *In re Smith*).
- Avoid exclamation marks. Avoid emoji entirely (see Iconography below).
- Verbs lead actions: *"Cite this passage,"* *"Open in workspace,"* *"Compare jurisdictions."*

**Pronouns**
- Address the user as **you** ("Your matters", "You haven't cited a source").
- Use **we** for product behavior or product opinions ("We pulled 12 citations from Westlaw…"). Rare. Default to user-centered.
- The AI refers to itself in third person if at all — *"LawGIQ found 4 relevant cases"* — not "I found".

**Vibe**
- Confident, precise, never overselling. Quantitative when possible ("12 of 14 cases are still good law") rather than vague ("most of these are fine").
- Plain English; legalese only when quoting actual law.
- Use the section sign `§`, `et al.`, `v.` correctly — small details signal credibility.

**Examples**

| Don't | Do |
|---|---|
| "🎉 We found amazing cases for you!" | "12 cases match. 9 are binding in your jurisdiction." |
| "Oops, something went wrong." | "We couldn't reach Westlaw. Retry, or upload the PDF directly." |
| "Get Started — It's Free!" | "Start a 14-day trial. No card required." |
| "Sources Available" | "Sources cited" |

**Empty states are useful.** Don't say "Nothing here yet" — say *"No documents in this matter. Drop a PDF or paste a citation."*

---

## Visual foundations

**Layout**
- 12-column grid, 24px gutters, 1200–1320px max container.
- Marketing pages use generous vertical rhythm (96–160px section padding). Product pages are dense — 16–24px between rows.
- Fixed header (64px) on web app. Marketing header is sticky on scroll, drops a hairline shadow when stuck.
- Sidebars are 280–320px, never collapsed on desktop.

**Backgrounds**
- **Bone (`#F5F5F5`)** is the default page background — never pure white.
- **Pure white** is reserved for elevated surfaces (cards, panels, modals).
- Subtle architectural pattern (`assets/bg-hero-columns.svg`) for marketing hero only — full-bleed, very low contrast.
- **No gradients** as fills. The only "gradient" we use is a horizontal ember rule as a section break.
- No hand-drawn illustrations. No textures. No grain.

**Imagery**
- Photography is **warm-neutral, naturally lit** — law offices, hands on paper, libraries, considered portraits. No stock-photo cliché (handshakes, gavels, blindfolded statues). Slight desaturation; never high-contrast.
- Product screenshots can be cropped close, slight slate ink shadow underneath.

**Borders**
- Default `1px solid var(--border)` (slate-100). Strong borders use `--border-strong`.
- Tables: horizontal rules only, no verticals.
- Inputs: 1px border, 6px radius, focus ring is a 3px teal glow + 1px teal border.

**Corner radii**
- Buttons & inputs: `6–10px`.
- Cards: `10–14px`.
- Pills / chips: `999px`.
- Modals: `14–20px`.
- The brand mark uses `8px` on a 56px square (~14% radius) — match that ratio for consistency.

**Shadows**
- Restrained — this is a legal product, not a floaty SaaS dashboard.
- `--shadow-sm` for resting cards. `--shadow-md` for menus, dropdowns. `--shadow-lg` for modals only.
- Focus shadow: `0 0 0 3px rgba(118,171,174,0.35)` — the teal glow.
- No colored shadows. No glows.

**Hover / press states**
- Buttons (primary): hover darkens to `--ember-600`; press to `--ember-700`. No scale.
- Buttons (secondary): hover adds a `--slate-50` background. Press darkens border.
- Links: hover underlines at 2px offset.
- Cards: hover lifts shadow `sm → md` and shifts border to `--border-strong`. No translate.
- **No transform-based hovers.** Nothing moves. Only color and shadow.

**Motion**
- Durations: `120ms` (fast — buttons, hovers), `180ms` (base — dropdowns, tabs), `260ms` (slow — modals, page transitions).
- Easing: `cubic-bezier(0.2, 0.7, 0.2, 1)` for entering things, `cubic-bezier(0.4, 0, 0.2, 1)` for symmetric transitions.
- **No bounce. No spring. No staggered cascades.** Things fade and slide a small distance. That's it.

**Transparency & blur**
- Backdrop blur reserved for sticky headers in scrolled state (`backdrop-filter: blur(10px)` over a `rgba(245,245,245,0.8)` surface).
- Modal scrims are `rgba(20,24,29,0.55)` — no blur, just darken.

**Highlighting (citations)**
- Cited text in source viewers uses `--highlight` (a warm parchment yellow) or `--highlight-teal` for advisory annotations.
- Highlights are *backgrounds*, not borders. Underlines are reserved for links.

---

## Iconography

**System:** [Lucide](https://lucide.dev) (via CDN, `lucide@latest`). 1.5px stroke, rounded line caps, 24px default — switch to 20px in dense UI rows, 16px inside buttons.

> **Substitution flag:** No icons were provided. Lucide was chosen for legibility, lawful (no kidding) neutrality, and excellent coverage of file/document/balance/clock metaphors that suit a legal product. **If LawGIQ has a custom icon set, drop the SVGs into `assets/icons/` and update the icon references in the UI kits.**

**Rules**
- Always stroke icons — never filled — unless indicating an active/selected state.
- Icon color matches surrounding text by default (`currentColor`).
- Ember is used for icons *only* on destructive/alert states; teal for informational; slate for everything else.
- Pair an icon with a label whenever space allows. Icon-only buttons must have a tooltip.

**No emoji.** Even in marketing copy, even in empty states. Use the brand glyph (`§`, `¶`, `et al.`) where you'd be tempted to use 🎉 or ⚖️.

**Unicode glyphs** in use: `§` (section sign, very on-brand), `¶` (pilcrow, for paragraph references), `—` (em dash, for asides), `·` (middot, for token separation). All other separation is done with spacing or hairlines.

**Brand glyph** (`assets/glyph-section.svg`) — a teal-plaque `§` — can be used as an avatar, app icon, or favicon when the full wordmark won't fit.

---

## A note on density

Legal users live in their tools. Optimize for **reading comprehension at 14px** — not for marketing aesthetics. Lists are tight. Tables are dense. White space is earned, not sprayed. The marketing site can breathe; the product cannot.

---

## SKILL.md

`SKILL.md` at the project root makes this whole folder usable as a portable Claude Skill — drop it into Claude Code and it can produce on-brand LawGIQ assets from the same foundations.
