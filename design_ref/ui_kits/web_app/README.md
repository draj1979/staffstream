# LawGIQ — Web App UI kit

A high-fidelity recreation of the LawGIQ product workspace. Three-pane layout: navigation, AI research conversation, source/citation panel.

## Files

| File | What it is |
|---|---|
| `index.html` | The mounted app — open this in a browser. Designed for **1280–1440px** width. |
| `App.jsx` | Top-level component, state, mock data (matters, authorities, source passages). |
| `Header.jsx` | App header — logo, matter switcher, global search, user. |
| `Sidebar.jsx` | Left rail — matters list, recent threads, library, settings. |
| `MainView.jsx` | Main work area — breadcrumbs, matter tabs, conversation, composer. Contains the `Cite`, `AuthorityRow`, `Composer`, `UserMsg`, `AiAnswer` subcomponents. |
| `SourcePanel.jsx` | Right rail — opened source document with highlighted passages, tags, actions. |
| `Icon.jsx` | Inline SVG icon set (Lucide-style). All icons used in the kit live here. |
| `styles.css` | Component CSS. Imports the global `colors_and_type.css` tokens. |

## Interactions wired up

- **Sidebar** — click any matter to switch the active matter (header & breadcrumbs update).
- **Citations** — click any `Cite` chip inline in the answer, or any `AuthorityRow`, and the right panel switches to that source. The active citation gets a teal highlight.
- **Composer** — type and hit Enter (or click *Ask LawGIQ*) to append a new user/ai exchange.
- **Close panel** — `×` in the source panel header collapses to an empty state.

## What's intentionally fake

- The AI answer is the same canned passage for every prompt — this is a UI kit, not a backend.
- Sidebar counts, "good law" / "distinguished" badges are static.
- Matter switching does not change the conversation content.

## Source of truth

No production LawGIQ codebase was provided, so this layout is **inferred from the brief and product category** — not lifted from real code. If a Figma file, codebase, or live product exists, reconcile this kit against it.
