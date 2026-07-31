---
name: lawgiq-design
description: Use this skill to generate well-branded interfaces and assets for LawGIQ, an AI-powered legal assistant platform — either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

Read the README.md file within this skill, and explore the other available files.

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.

If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

## Quick orientation

- **Tokens** — every color, type, spacing, radius, shadow, and motion value lives in `colors_and_type.css`. Always import it; never reinvent values.
- **Brand thesis** — editorial authority (legal tradition) meets considered AI tooling. Sober base, single ember accent. No emoji. No bouncing animations. No purple gradients.
- **Type pairing** — Instrument Serif (display, italic-friendly), Geist (UI/body), JetBrains Mono (citations). Loaded from Google Fonts.
- **Voice** — counsel, not pep talk. Sentence case. Quantitative. See README → Content fundamentals.
- **Logo** — `assets/logo-wordmark.svg` for light backgrounds, `assets/logo-wordmark-inverse.svg` for dark, `assets/logo-mark.svg` for square placements (favicons, avatars).
- **Iconography** — Lucide via CDN, 1.5px stroke, stroke-only (no fills). The web app's `Icon.jsx` has the inline set if you want to keep things self-contained.
- **UI patterns** — see `ui_kits/web_app/` (product workspace) and `ui_kits/marketing_site/` (homepage) for reference compositions you can crib from or extend.

## When designing something new

1. Read `README.md` end-to-end. It encodes the rules.
2. Import `colors_and_type.css`. Use the CSS variables — `var(--ember-500)`, `var(--fg1)`, etc.
3. Pull from the UI kits when possible: the workspace shell, the citation chip, the authority row, the dark-section quote, the editorial hero — these are tested patterns.
4. Show your work — produce HTML (not screenshots) so the user can review at fidelity.

## Common pitfalls to avoid

- Don't use ember as a body color or fill — it is a single accent.
- Don't use pure white as a page background — bone (`#F5F5F5`) is the default.
- Don't use serif for UI labels or buttons — Geist only there. Serif is for display, marketing, and quoted passages.
- Don't add emoji. Use the brand glyph (§) or unicode (¶, —, ·) instead.
- Don't animate with bounce/spring. 120/180/260ms with the standard easings. Fades and short slides only.
