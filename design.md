# design.md — LoopClose UI/UX Specification

> Any AI agent must be able to build the **same** UI from this file alone. Use these tokens, components and layouts exactly. Do not introduce new colours, fonts or component styles without logging a decision in `memory.md`.
> Implementation: server-rendered **Jinja2 + HTMX**, hand-written CSS in `app/static/css/app.css`. No UI frameworks, no Tailwind, no icon fonts.

---

## 1. Design principles

1. **Calm and clear.** A work tool people open daily: light, quiet, generous whitespace, one strong accent colour.
2. **Status at a glance.** Colour-coded badges for status, overdue, risk, and AI-generated content are the main visual language.
3. **AI is visibly assistive, never silent.** AI-generated content always carries the "AI" pill; AI proposals are reviewed before saving; failures are explained in plain language with a retry.
4. **Progressive disclosure.** Meeting detail uses tabs; history is a timeline, not a wall of text.
5. **No emoji in UI chrome.** Use inline SVG icons (simple 1.75px-stroke line icons, 16–20px) or text.
6. **Accessible by default.** WCAG AA contrast, visible focus rings, labelled controls, keyboard operable.

---

## 2. Design tokens (CSS variables)

Define in `:root` and override in dark mode. Components must reference variables only — never raw hex values.

```css
:root {
  /* Surfaces */
  --bg: #F6F7FB;
  --surface: #FFFFFF;
  --surface-2: #EEF0F6;       /* subtle fills, table headers, code */
  --border: #E1E5EE;
  --border-strong: #C9CFDD;

  /* Text */
  --text: #151A24;
  --text-muted: #566074;
  --text-faint: #7B8498;
  --text-on-primary: #FFFFFF;

  /* Brand */
  --primary: #4F46E5;          /* indigo */
  --primary-hover: #4338CA;
  --primary-soft: #EEF0FF;
  --focus-ring: #4F46E5;

  /* AI accent (violet) — used ONLY for AI-generated/AI-assisted UI */
  --ai: #7C3AED;
  --ai-soft: #F3EEFF;
  --ai-border: #DCCBFB;

  /* Semantic */
  --success: #15803D;  --success-soft: #DCF5E4;
  --warning: #92400E;  --warning-soft: #FEF0D0;
  --danger:  #B91C1C;  --danger-soft:  #FDE2E2;
  --info:    #1D4ED8;  --info-soft:    #E0ECFF;
  --neutral: #4B5563;  --neutral-soft: #ECEEF2;

  /* Priority edge colours (left border on item cards) */
  --prio-high: #DC2626;
  --prio-medium: #D97706;
  --prio-low: #94A3B8;

  /* Radius, shadow, spacing */
  --radius-sm: 6px;  --radius-md: 10px;  --radius-pill: 999px;
  --shadow-sm: 0 1px 2px rgba(16,24,40,.06);
  --shadow-md: 0 6px 18px rgba(16,24,40,.10);
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-5: 24px; --space-6: 32px; --space-7: 48px;

  /* Layout */
  --container: 1120px;
  --nav-height: 56px;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0E1117;  --surface: #171B24;  --surface-2: #1F2430;
    --border: #2A3140;  --border-strong: #3A4357;
    --text: #E8EBF3;  --text-muted: #A3ACBF;  --text-faint: #7F889C;
    --primary: #818CF8;  --primary-hover: #A5B4FC;  --primary-soft: #232647;
    --text-on-primary: #0E1117;  --focus-ring: #A5B4FC;
    --ai: #A78BFA;  --ai-soft: #272046;  --ai-border: #453A78;
    --success: #4ADE80;  --success-soft: #12301E;
    --warning: #FBBF24;  --warning-soft: #3A2A0B;
    --danger:  #F87171;  --danger-soft:  #3B1515;
    --info:    #7DB1FF;  --info-soft:    #14264A;
    --neutral: #9CA3AF;  --neutral-soft: #262B36;
    --shadow-sm: 0 1px 2px rgba(0,0,0,.4);
    --shadow-md: 0 6px 18px rgba(0,0,0,.5);
  }
}
```

### Typography
- **Font family:** `Inter` (Google Fonts, weights 400/500/600/700, `display=swap`) with fallback `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`.
- **Mono (IDs, request IDs, code):** `ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace`.
- **Scale (size / line-height / weight):**

| Token | Use | Size / LH | Weight |
|---|---|---|---|
| `h1` | Page title | 28px / 36px | 700 |
| `h2` | Section title | 20px / 28px | 600 |
| `h3` | Card title | 16px / 24px | 600 |
| `body` | Default | 15px / 24px | 400 |
| `small` | Meta, captions | 13px / 20px | 400 |
| `label` | Form labels, table headers | 12px / 16px, uppercase tracking .04em | 600 |

- Numbers in tables use `font-variant-numeric: tabular-nums`.

### Spacing & layout
- 4px base unit. Card padding 16–24px; section gap 24px; form field gap 16px.
- Page container: `max-width: var(--container); margin: 0 auto; padding: 0 16px`.
- Breakpoints: **≤640px** mobile (single column, nav collapses to a menu button), **641–1023px** tablet (2 columns max), **≥1024px** desktop (up to 3 columns in dashboard).
- Grid helpers: `.grid-2`, `.grid-3` (collapse to 1 column ≤640px / 2 columns ≤1023px).

---

## 3. Global layout

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ [◎ LoopClose]  Dashboard  Meetings  Items  Knowledge  Nudges   Viewing as [Priya ▾] │  ← sticky top nav, 56px
├───────────────────────────────────────────────────────────────────────────────┤
│  Page title (h1)                                        [Primary action button] │
│  breadcrumb / meta line (small, muted)                                          │
│                                                                                 │
│  content (cards / tables / tabs)                                                │
└───────────────────────────────────────────────────────────────────────────────┘
        toast area: fixed bottom-right (stack), aria-live="polite"
```

- **Top nav:** surface background, bottom border, sticky. Logo = small indigo rounded square with a "closed loop" SVG + wordmark "LoopClose" (600). Active link: `--primary` text + 2px bottom bar. Nudges link shows a small danger-coloured count pill when High-risk items exist.
- **"Viewing as" selector:** compact `<select>` styled as pill; change posts via HTMX and reloads the page.
- **Footer:** small muted line: app name · environment tag (only when not production) · "Request ID" (mono) for debugging.

---

## 4. Components

### 4.1 Buttons
| Variant | Style |
|---|---|
| Primary | bg `--primary`, text `--text-on-primary`, radius 6, padding 8×14, weight 600; hover `--primary-hover` |
| Secondary | bg `--surface`, 1px `--border-strong`, text `--text`; hover bg `--surface-2` |
| Ghost | transparent, text `--primary`; hover bg `--primary-soft` |
| Danger | bg `--danger-soft`, text `--danger`, 1px solid `--danger`; hover slightly darker |
| **AI button** | bg `--ai-soft`, text `--ai`, 1px `--ai-border`, **sparkle icon** left; hover: border `--ai`. Use for every action that calls AI ("Generate recap", "Generate brief", "Suggest related", "Draft follow-up") |
- Disabled: 50% opacity, `cursor: not-allowed`. Loading (HTMX `htmx-request`): replace label with spinner + "Working…", disable button.
- Min touch target 40px height on mobile.

### 4.2 Forms
- Label above input (label style). Inputs: height 40px, 1px `--border-strong`, radius 6, bg `--surface`, padding 0 12px; textarea min-height 96px (notes: 240px).
- Focus: 2px outline `--focus-ring` with 2px offset. Error: border `--danger`, message below in `--danger` small text with `role="alert"`.
- Helper text: small muted below field. Required marker: none (use "optional" label text for optional fields).
- Date/time use native `<input type="date">` / `datetime-local`.
- Participants: checklist of people with a small attendance `<select>` beside each.

### 4.3 Cards
`bg --surface`, 1px `--border`, radius 10, `--shadow-sm`, padding 16–24. Card header row: title (h3) left, actions right. Clickable cards lift to `--shadow-md` on hover.

### 4.4 Badges / pills (radius pill, 12px/16px text, weight 600, padding 2×8)
| Badge | Text | Colours |
|---|---|---|
| Item `open` | Open | `--info` on `--info-soft` |
| Item `in_progress` | In progress | `--warning` on `--warning-soft` |
| Item `blocked` | Blocked | `--danger` on `--danger-soft` |
| Item `done` | Done | `--success` on `--success-soft` |
| Item `dropped` | Dropped | `--neutral` on `--neutral-soft` |
| Overdue chip | "Overdue 3d" | solid `--danger` bg, white text (dark mode: `--danger-soft` bg + `--danger` text) |
| Unassigned chip | "Needs owner" | `--warning` on `--warning-soft`, dashed border |
| Meeting `planned` | Planned | `--info` on `--info-soft` |
| Meeting `held` | Held | `--primary` on `--primary-soft` |
| Meeting `closed` | Closed | `--success` on `--success-soft` |
| Meeting `cancelled` | Cancelled | `--neutral` on `--neutral-soft`, strikethrough title |
| Kind `handover` | Handover | `--primary` outline pill with arrow-right icon; `meeting` kind has no extra pill |
| Risk High / Medium / Low | High / Medium / Low | danger / warning / neutral palettes |
| Attendance | Attended (success), Absent (danger), No response (warning), Declined (neutral), Invited (info) | |
| **AI pill** | `✦ AI` (sparkle SVG + "AI") | `--ai` on `--ai-soft`, 1px `--ai-border`. Shown on any AI-generated row/section until a human edits it |
| Method pill (links) | "AI match", "Semantic", "Keyword", "Manual" | neutral-soft; Semantic/AI use AI palette |
| Carried chip | "Carried 3×" | `--warning` palette; shown when `carried_count ≥ 1` (tooltip: origin meeting) |

### 4.5 Tables and lists
- Header row: `--surface-2` bg, label style. Row height ≥ 48px, 1px bottom `--border`, hover `--surface-2`.
- Item rows (list view): `[priority edge] Title (h3-ish 15px/600) · badges row · Owner avatar+name · Due date · actions`. Priority edge = 4px left border in `--prio-*`.
- Wide tables scroll horizontally inside `overflow-x:auto` wrapper; on mobile, item rows collapse to **stacked cards**.
- **Avatar:** 28px circle with initials, background chosen deterministically from a 6-colour pastel set by person id.

### 4.6 Tabs (meeting detail)
Horizontal tab bar under the header; active tab: `--primary` text + 2px bottom border. Tabs load via HTMX (`hx-get`, `hx-target="#tab-panel"`, `hx-push-url="true"`). On mobile the bar scrolls horizontally.

### 4.7 Timeline (history)
Vertical line (`--border-strong`) with 10px dots; dot colour by event type (created=info, reassigned=primary, status_changed=warning, carried_forward=warning, closed=success, nudged=ai, kb_linked=ai). Each entry: **title line** ("Reassigned: Priya → Rohan"), muted meta ("30 Oct 2026, 9:14 · by user · in 'Vendor sync'"), optional note.

### 4.8 Toasts and banners
- **Toast:** bottom-right, surface bg, 1px border, left accent bar (success/danger/info), auto-dismiss 5 s, close button, `role="status"`.
- **Banner (inline):** full-width inside card, tinted bg + icon + text + optional action.
  - AI fallback banner: `--warning-soft`, text "AI is unavailable right now — showing a basic version." + **Retry** secondary button.
  - AI error banner uses danger palette only when nothing could be produced.
  - Validation summary banner at top of a form when ≥2 errors.

### 4.9 Empty states
Centered, muted: simple line icon (48px), one-sentence explanation, one primary action. Examples: "No meetings yet — Create your first meeting", "Nothing to nudge. All items are on track."

### 4.10 Loading and AI "thinking"
- HTMX indicator: inline spinner (16px, CSS-only) + text. For AI actions show a **skeleton block** (3 shimmering bars) in the target area with caption "AI is reading your notes… this can take a few seconds."
- Never block the whole page; the rest of the UI stays usable.

### 4.11 Modals/confirm
Avoid modals. Use inline expanding panels (e.g. the **Close item** form expands inside the row/detail with outcome select + textarea). Destructive confirms use `hx-confirm`.

---

## 5. Pages and layouts

### 5.1 Dashboard `/`
Three-column grid on desktop (stacks on mobile):
```
┌ My open items (viewing as X) ───────┐ ┌ Needs attention ───────────┐ ┌ Upcoming meetings ───┐
│ [item row] [item row] ... View all  │ │ Overdue: 3   Needs owner: 1 │ │ Tue 3 Nov · Sprint… │
│                                      │ │ High-risk nudges: 4 [Open]  │ │ Fri 6 Nov · Handover│
└──────────────────────────────────────┘ └─────────────────────────────┘ └──────────────────────┘
┌ Recent decisions ─────────────────────────────────────────────────────────────────────────────┐
│ • Decision text — Meeting title · date                                                         │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```
Stat tiles: number in 28px/700, label below (small, muted); danger-coloured when >0 for Overdue.

### 5.2 Meetings list `/meetings`
Header with filters (kind, status as pill-style segmented controls) and **New meeting** primary button. Table columns: Title (with kind pill) · Date · Status · Participants (avatar stack, max 4 + "+n") · Open items (count) · Actions.

### 5.3 New meeting `/meetings/new`
Single-column form card (max-width 720px): Kind (segmented: Meeting | Handover) → Title → Date & time → Agenda (textarea) → Participants (checklist + attendance) → *if Handover:* From / To selects → *Optional:* "Continue from previous meeting" select + "Carry forward N open items" checkbox (default on). Primary: **Create**. Secondary: **Cancel**.

### 5.4 Meeting detail `/meetings/{id}`
```
┌ Title (h1)  [Kind pill][Status badge]                            [Change status ▾] [Edit] ┐
│ Fri 6 Nov 2026, 10:30 · 5 participants · 4 open items                                      │
├ Tabs:  Overview | Notes & Recap | Items | Brief | Knowledge | History                     ┤
├────────────────────────────────────────────────────────────────────────────────────────────┤
│ OVERVIEW:   Agenda card · Participants card (avatar, name, attendance select) ·           │
│             Carried-over items card (if any) · Decisions card (+ add)                      │
│ NOTES & RECAP: big textarea [Save notes]  [✦ Generate recap]                              │
│             → Recap review card (AI pill): Summary (editable) · Decisions (checkbox rows) │
│               · Action items (checkbox, title, owner select, due date, priority)           │
│               · Open questions · [Apply selected] [Discard]                                │
│ ITEMS:      Item list for this meeting + "Add item" inline form                            │
│ BRIEF:      "Brief for [person ▾]" [✦ Generate brief] → brief card                        │
│ KNOWLEDGE:  Linked documents + [✦ Suggest related] + manual add                            │
│ HISTORY:    Timeline of all item events for this meeting                                   │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```
- Handover meetings add a prominent info card at top of Overview: "**Priya → Rohan** · 5 open items owned by Priya · [Reassign all to Rohan]".
- Closed meetings: read-only banner; **Carry forward** card appears when open items remain ("4 open items weren't finished. Carry them to: [select next meeting ▾] [Carry forward]  or [Create next meeting]").

### 5.5 Item detail `/items/{id}`
Two-column (main + side) on desktop:
- **Main:** Title, description, status badge row (status, overdue, carried, AI), **Actions**: Start / Block / Reassign / Edit due / **Close with outcome** (expanding panel) / Reopen. Then **Linked knowledge** (document title, method pill, reason; remove button) with **✦ Suggest related**. Then **History timeline**.
- **Side card:** Owner (avatar+name), Due date (red when overdue), Priority, Origin meeting (link), Current meeting (link), Carried count, Last nudged, Outcome (if closed).

### 5.6 Items list `/items`
Filter bar (status multi-select chips, owner select, "Overdue only" toggle, meeting select), sortable by due date (default), then a list of item rows (see 4.5). Footer count: "Showing 12 of 14".

### 5.7 Knowledge `/kb`, `/kb/new`, `/kb/{id}`
- List: grid of cards (title, type pill, summary 2 lines clamp, tags, "Referenced by N items"). Search box (client-side filter over titles/tags is fine). **Add document** primary.
- New: Title, Type select, Content textarea (tall) **or** upload `.txt/.md`; helper "AI will write a short summary and tags."
- Detail: title, type pill, AI pill on summary, tags, content (pre-wrap, max-height scroll), "Referenced by" list.
- *(Unit 9)* **Ask Team Memory** page `/ask`: single question input, answer card with citations as pills linking to documents; caption "Answers use only your team's documents."

### 5.8 Nudge Center `/nudges` (special feature)
```
┌ Nudge Center — items that need a follow-up ─────────────────────────────────────────────┐
│ Filter: [All owners ▾]  Risk: [High][Medium][Low]                                        │
│ ── Owner: Karan Shah (3) ──────────────────────────────────────────────────────────────  │
│ ┌ [HIGH] Update vendor SLA draft                                  Due 25 Oct · Overdue 5d ┐│
│ │ Chips: Overdue 5d · Carried 3× · High priority                                          ││
│ │ [Friendly | Firm]  [✦ Draft follow-up]                                                  ││
│ │ ┌ Draft (AI pill) ───────────────────────────────────────────────────────────────────┐ ││
│ │ │ Hi Karan, quick check on …                                      [Copy] [Mark sent] │ ││
│ │ └────────────────────────────────────────────────────────────────────────────────────┘ ││
│ └──────────────────────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────────────────┘
```
Empty state: "Nothing to nudge. All items are on track."

### 5.9 People `/people`
Simple table + "Add person" inline form. Inactive people shown muted with "On leave" chip.

### 5.10 Error pages
Friendly page (404 "We can't find that", 500 "Something went wrong") with illustration-free layout, a **Back to dashboard** button, and the **Request ID** in mono text with copy button.

---

## 6. Interaction patterns (HTMX)

| Pattern | Implementation |
|---|---|
| Partial updates | Routes check `HX-Request`; return partial template; `hx-target` the section; `hx-swap="outerHTML"` or `innerHTML` as appropriate |
| Forms | `hx-post`; on validation error return the **form partial with errors** (HTTP 422, `hx-swap="outerHTML"`; enable `htmx.config.responseHandling` or equivalent to swap 4xx for 422) |
| AI actions | Button `hx-post`, `hx-indicator` + skeleton in target, `hx-disabled-elt="this"` |
| Toasts | Response header `HX-Trigger: {"toast": {"type":"success","message":"..."}}`; `app.js` listens and renders |
| Status change | Row re-rendered in place (optimistic feel, no page reload) |
| Navigation | Standard links; tab changes use `hx-push-url` so URLs are shareable |
| Confirm | `hx-confirm` for delete / cancel meeting / mark dropped |

`app.js` scope (≤ ~80 lines): toast rendering, tab active state, copy-to-clipboard buttons, auto-dismiss, "Viewing as" change. No other JS.

---

## 7. Copy and tone

- Plain, friendly, concise. Sentence case everywhere (buttons too): "Generate recap", "Carry forward", "Close item".
- Explain AI limits honestly: "AI suggestions may be wrong — review before applying."
- Errors say what happened + what to do: "We couldn't reach the AI service. Your notes are saved. Try again in a moment."
- Dates: `30 Oct 2026` (day-month-year), times 24h `10:30`; relative hints in muted text ("in 3 days", "5 days overdue").
- Use the person's name in nudges/briefs; never expose internal IDs except the request ID on error pages.

---

## 8. Accessibility checklist (must pass before Unit 8 is done)

- All interactive elements reachable by Tab, visible focus ring (2px `--focus-ring`).
- Colour is never the only signal: badges include text; overdue has text "Overdue Nd".
- Inputs have `<label for>`; errors use `role="alert"` and `aria-describedby`.
- Toast container `aria-live="polite"`; AI loading regions `aria-busy="true"`.
- Tabs use `role="tablist" / "tab" / "tabpanel"` and `aria-selected`.
- Text contrast ≥ 4.5:1 (tokens above are chosen for this; re-check any new colour).
- Respect `prefers-reduced-motion` (disable shimmer/transitions).
- `<html lang="en">`, one `<h1>` per page, landmark elements (`header`, `nav`, `main`, `footer`).

---

## 9. Iconography

Inline SVG sprite in `base.html` (`<symbol>` set), 20px default, `stroke="currentColor"`, `stroke-width="1.75"`, round caps/joins. Required icons: sparkle (AI), loop (logo), calendar, users, check-circle, alert-triangle, clock, arrow-right, arrow-repeat (carry), link, book (KB), bell (nudge), copy, plus, x, chevron-down, edit, user.

---

## 10. Motion

- Transitions 120–160ms ease-out on hover/focus/background only.
- Skeleton shimmer 1.2s linear infinite (disabled under reduced motion).
- No page transitions, no bouncing, no parallax.
