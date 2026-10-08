---
name: QEOS
description: Self-hosted test-results analytics; an authenticated Operate surface for triaging CI and reading suite health.
colors:
  page: "#f5f6fb"
  surface-1: "#ffffff"
  surface-2: "#eceefa"
  hover: "rgba(21, 26, 51, 0.05)"
  hover-strong: "rgba(79, 70, 229, 0.09)"
  text-primary: "#151a33"
  text-secondary: "#4c5470"
  text-muted: "#7d839f"
  grid: "#e4e7f2"
  border: "rgba(21, 26, 51, 0.1)"
  border-strong: "rgba(21, 26, 51, 0.18)"
  accent: "#4f46e5"
  accent-text: "#4338ca"
  accent-soft: "rgba(79, 70, 229, 0.1)"
  accent-fill: "#4f46e5"
  accent-fill-hover: "#4338ca"
  series-1: "#4f46e5"
  series-2: "#eb6834"
  status-passed: "#0ca30c"
  status-failed: "#d03b3b"
  status-errored: "#c4501f"
  control-border: "#7a809c"
  placeholder: "#5f6580"
  status-skipped: "#7d839f"
  danger-text: "#c23434"
  danger-fill-hover: "#b83131"
  on-fill: "#ffffff"
  page-dark: "#0b1020"
  surface-1-dark: "#141c33"
  surface-2-dark: "#0f1629"
  hover-dark: "rgba(165, 180, 252, 0.06)"
  hover-strong-dark: "rgba(129, 140, 248, 0.15)"
  text-primary-dark: "#eef1fb"
  text-secondary-dark: "#a9b2cc"
  grid-dark: "#222b45"
  border-dark: "rgba(148, 163, 214, 0.14)"
  border-strong-dark: "rgba(148, 163, 214, 0.24)"
  accent-dark: "#818cf8"
  accent-text-dark: "#a5b4fc"
  accent-soft-dark: "rgba(129, 140, 248, 0.18)"
  series-1-dark: "#818cf8"
  series-2-dark: "#d95926"
  danger-text-dark: "#f08080"
  status-errored-dark: "#ec835a"
  control-border-dark: "#6f7a9c"
  placeholder-dark: "#a3abc6"
typography:
  headline:
    fontFamily: "\"Inter Variable\", system-ui, -apple-system, \"Segoe UI\", Roboto, sans-serif"
    fontSize: "22px"
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "-0.01em"
  title:
    fontFamily: "\"Inter Variable\", system-ui, -apple-system, \"Segoe UI\", Roboto, sans-serif"
    fontSize: "17px"
    fontWeight: 600
    lineHeight: 1.3
  title-small:
    fontFamily: "\"Inter Variable\", system-ui, -apple-system, \"Segoe UI\", Roboto, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.35
  stat:
    fontFamily: "\"Inter Variable\", system-ui, -apple-system, \"Segoe UI\", Roboto, sans-serif"
    fontSize: "28px"
    fontWeight: 650
    letterSpacing: "-0.01em"
    fontFeature: "\"tnum\""
  body:
    fontFamily: "\"Inter Variable\", system-ui, -apple-system, \"Segoe UI\", Roboto, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "\"Inter Variable\", system-ui, -apple-system, \"Segoe UI\", Roboto, sans-serif"
    fontSize: "13px"
    fontWeight: 500
  label-small:
    fontFamily: "\"Inter Variable\", system-ui, -apple-system, \"Segoe UI\", Roboto, sans-serif"
    fontSize: "12.5px"
    fontWeight: 600
  mono:
    fontFamily: "ui-monospace, \"SF Mono\", \"Cascadia Mono\", Consolas, monospace"
    fontSize: "12.5px"
rounded:
  sm: "6px"
  md: "10px"
  pill: "999px"
spacing:
  space-1: "4px"
  space-2: "8px"
  space-3: "12px"
  space-4: "16px"
  space-5: "24px"
  space-6: "32px"
  space-7: "48px"
  sidebar-width: "240px"
components:
  button:
    backgroundColor: "{colors.surface-1}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.sm}"
    padding: "6px 10px"
    height: "34px"
  button-hover:
    backgroundColor: "{colors.hover-strong}"
  button-primary:
    backgroundColor: "{colors.accent-fill}"
    textColor: "{colors.on-fill}"
    rounded: "{rounded.sm}"
    padding: "6px 10px"
    height: "34px"
  button-primary-hover:
    backgroundColor: "{colors.accent-fill-hover}"
  button-danger:
    backgroundColor: "{colors.status-failed}"
    textColor: "{colors.on-fill}"
    rounded: "{rounded.sm}"
    padding: "6px 10px"
    height: "34px"
  button-danger-hover:
    backgroundColor: "{colors.danger-fill-hover}"
  button-ghost:
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.sm}"
    padding: "7px 12px"
  input:
    backgroundColor: "{colors.surface-1}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.sm}"
    padding: "6px 10px"
    height: "34px"
  card:
    backgroundColor: "{colors.surface-1}"
    rounded: "{rounded.md}"
    padding: "{spacing.space-5}"
  nav-link:
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.sm}"
    padding: "7px 12px"
    height: "34px"
  nav-link-active:
    backgroundColor: "{colors.surface-1}"
    textColor: "{colors.text-primary}"
  badge:
    backgroundColor: "{colors.surface-1}"
    typography: "{typography.label-small}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"
  badge-failed:
    textColor: "{colors.danger-text}"
  sidebar:
    backgroundColor: "{colors.surface-2}"
    width: "{spacing.sidebar-width}"
    padding: "16px 12px"
  project-tile:
    backgroundColor: "{colors.surface-1}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    padding: "{spacing.space-4}"
  code-block:
    backgroundColor: "{colors.page}"
    typography: "{typography.mono}"
    rounded: "{rounded.sm}"
    padding: "{spacing.space-3}"
---

# Design System: QEOS

## Overview

**Creative North Star: "The Triage Desk"**

QEOS is an internal Operate surface. People open it after a red build or in a weekly review, and every visual decision serves one question: what is broken, what is flaky, what is getting worse. The system is restrained on purpose. Cool indigo-tinted neutrals (navy in dark mode) carry the structure, one indigo accent marks interaction and location, and the four validated status hues are kept for test outcomes only. Since nothing else on screen is saturated, a red dot means a failure.

Density is moderate. The body text is 14px with an 8px-based spacing scale. Cards, tables and tiles sit on a quiet page tone, and a persistent left sidebar holds the project switcher and every view. Light and dark are both first-class and follow the OS (`prefers-color-scheme`). There is no manual toggle. Every text pair is computed against its actual background in both themes and clears WCAG AA (4.5:1). Where a hue fails that test, the system adds a separate text token rather than accepting the miss.

Depth is light and ambient: hairline borders do the structural work, and a faint shadow lifts cards off the page. Motion is short and functional (120ms colour/border transitions, a 200ms drawer slide) and switches off under `prefers-reduced-motion`.

**Key Characteristics:**
- Midnight Indigo: cool indigo-tinted neutrals, one indigo accent, status hues reserved for status.
- Every readable text pair is at least 4.5:1 in both themes. Each accent and danger hue has a separate role token for text and for fill.
- Status is never colour alone. A word or label always sits beside the hue.
- Sidebar shell with project switcher. Under 900px it becomes a focus-managed drawer.
- Icons come only from lucide-react, marked `aria-hidden`, and always sit beside visible text or inside an `aria-label`ed control.
- Touch targets are 44px under `pointer: coarse`. Body text grows to 16px under 640px.

## Colors

The palette (Midnight Indigo, chosen 2026-10-08) is a cool indigo-tinted neutral — navy surfaces in dark mode — with one interaction indigo, plus a colour-blind-validated status set that never decorates. Dark-theme counterparts carry the `-dark` suffix in the frontmatter. Status hues, `accent-fill` and `on-fill` are the same in both themes.

### Primary
- **Signal Indigo** (`accent`): focus rings, text selection, the active nav icon, the brand mark, project-tile hover border (6.3:1 on white; `#818cf8` in dark, 5.7:1 on Paper).
- **Link Indigo** (`accent-text`): all links and any accent text (7.9:1 on white; the dark value `#a5b4fc` is 8.5:1 on Paper).
- **Button Indigo** (`accent-fill`, hover `accent-fill-hover`): the fill of primary buttons only. White on it measures 6.3:1 (hover 7.9:1). The same value is kept in dark mode so white text stays legible.
- **Indigo Wash** (`accent-soft`): a translucent tint of the accent for soft selected states.

### Status (reserved)
- **Passed Green** (`status-passed`), **Failed Red** (`status-failed`), **Errored Orange** (`status-errored`), **Skipped Stone** (`status-skipped`): the validated status palette from PRODUCT.md. Use them for status dots, chart series of outcomes and badge icons. A status colour is always followed by its word or a label naming it, and never stands alone as a shape: dots, badges and chart bars also differ by shape or texture (see Status Dot and Badges, Chart Textures). Errored Orange is `#c4501f` in light (4.65:1 on Paper, 4.31:1 on Mist Page) and `#ec835a` in dark (6.40:1 on Paper). Every status colour reaches 3:1 on Paper in both themes; `lib/contrast.test.ts` checks it.
- **Danger Text** (`danger-text`): error copy, the error banner border and text, and the failed badge label. It exists because the dot red is a chart/dot hue, not a text colour. It measures 4.6:1 on the banner's red tint in light and 6.0:1 in dark.
- **Danger Fill** (`status-failed`, hover `danger-fill-hover`): the confirm button of a destructive action. White on it measures 4.8:1 in both themes, while red *text* on the dark surface would fail AA.

### Chart Series
- **Series Indigo** (`series-1`) and **Series Ember** (`series-2`): the two lines of a comparison chart, such as branch A against branch B. They are for non-status series only.

### Neutral
- **Mist Page** (`page`; navy `#0b1020` in dark): the app background. Code blocks also use it to sit one step below the card surface.
- **Paper** (`surface-1`; `#141c33` in dark): cards, inputs, buttons, tiles, badges and the active nav item.
- **Sidebar Mist** (`surface-2`): the sidebar and the narrow-screen top bar.
- **Ink** (`text-primary`): headings, body and values.
- **Graphite** (`text-secondary`): all readable secondary text, including labels, metadata, table headers, `.muted` copy and inactive nav (7.5:1 light, 8.0:1 dark).
- **Tick Grey** (`text-muted`): chart axis ticks only. It is below AA for text (about 3.7:1) and must never carry readable copy.
- **Rule** (`grid`): table row dividers and list separators.
- **Hairline** (`border`) and **Hairline Strong** (`border-strong`): translucent borders for containers and for buttons.
- **Control Edge** (`control-border`): the border of inputs, selects, textareas and checkboxes, at least 3:1 against every surface they sit on (WCAG 1.4.11). Light `#7a809c`: 3.89 on Paper, 3.61 on Mist Page, 3.37 on Sidebar Mist. Dark `#6f7a9c`: 3.97 on Paper, 4.23 on Sidebar Mist, 4.45 on Mist Page. Used for form controls only, so the rest of the interface stays light.
- **Placeholder** (`placeholder`): placeholder text at full opacity, at least 4.5:1 (light `#5f6580`: 5.74 on Paper, 4.97 on Sidebar Mist; dark `#a3abc6`: 7.40 on Paper).
- **Hover** (`hover`) and **Hover Strong** (`hover-strong`): translucent washes for row hover and button/nav hover; Hover Strong is indigo-tinted and also fills label tags.

### Named Rules
**The Reserved Hue Rule.** Green, red, orange and skipped-stone mean test outcomes. They never decorate, brand or highlight anything else. The only non-status uses are destructive confirmation (red fill) and error messaging (danger text), and both mean "something failed or will be destroyed".

**The Never Alone Rule.** A status colour is never the only signal. Every dot, badge and series carries its word ("12 failed", "Passed") or a legend.

**The Computed Pair Rule.** No text/background pair ships without being computed at 4.5:1 or better in both themes. When a hue fails, add a role token (`-text`, `-fill`) instead of using the hue anyway.

## Typography

**Display Font:** none (the product has no display role)
**Body Font:** Inter (variable, self-hosted via `@fontsource-variable/inter`), falling back to the system UI stack
**Label/Mono Font:** ui-monospace stack (ui-monospace, "SF Mono", "Cascadia Mono", Consolas, monospace)

**Character:** A single sans family across every role, separated by weight (500 to 650) and small size steps rather than by contrasting faces. Mono marks machine text such as commit SHAs, failure messages and CI snippets.

### Hierarchy
- **Headline** (650, 22px, 1.25, -0.01em): the one page heading, which is the project name or view name.
- **Title** (600, 17px, 1.3): card and section headings.
- **Title Small** (600, 15px, 1.35): sub-section headings.
- **Stat** (650, 28px, tabular figures, -0.01em): the single headline number in an overview card. The tile value is a 26px sibling.
- **Body** (400, 14px, 1.5): everything else. It rises to 16px under 640px, because iOS zooms into inputs below 16px and phones read better at that size.
- **Label** (500, 13px): form labels, metadata rows and tile labels, in Graphite.
- **Label Small** (600, 12.5px): table headers and badges. Sidebar section titles and the switcher label use 12px/600.
- **Mono** (12.5px, or 0.92em inline): failure messages, SHAs and code blocks.

### Named Rules
**The Tabular Numbers Rule.** Tables, tiles and stat figures use `font-variant-numeric: tabular-nums` so columns of counts and rates align.

**The 16px Phone Rule.** Body text is 14px on desktop and 16px at 640px and below. Do not set input text below the body size.

## Layout

An app shell runs the full height of the viewport: a fixed-width sidebar (240px) on Sidebar Mist and a fluid main column. Content sits in a centred page container (max 1120px) with 32px/24px padding, reduced to 24px/16px under 640px. Single-card focus pages (sign in, register, verify) narrow to 400px with 48px top padding.

Spacing follows a 4px-based scale (4, 8, 12, 16, 24, 32, 48). Cards own their vertical rhythm through 16px block margins, which collapse between siblings so conditional stacks stay evenly spaced. Inside a grid, the grid gap owns the spacing and card margins are zeroed.

Grids are auto-fitting rather than column-counted:
- **Overview grid:** `auto-fit, minmax(260px, 1fr)` with a 16px gap. A *wide* card spans the full row; the latest run gets this.
- **Tiles:** `auto-fit, minmax(170px, 1fr)` with a 12px gap.
- **Project grid:** `auto-fill, minmax(220px, 1fr)` with a 12px gap.

Breakpoints:
- **900px and below:** the sidebar becomes an off-canvas drawer (min(85vw, 300px)) behind a sticky top bar with a menu button. A 40% black backdrop closes it.
- **640px and below:** body text goes to 16px and page and card padding tighten.
- **`pointer: coarse`:** inputs, selects, buttons and nav links grow to a 44px minimum height, and table cells to 12px padding, without changing density on mouse devices.

### Named Rules
**The Grid Gap Owns It Rule.** Inside a grid, children carry no margins. Outside one, a card's own block margin sets the rhythm.

**The Coarse Pointer Rule.** Every interactive control reaches 44px under `pointer: coarse`.

## Elevation & Depth

The system is a hybrid that leans flat. Hairline borders carry structure, and two ambient shadow levels exist. Shadows never signal status and are never hard-edged or offset.

### Shadow Vocabulary
- **Resting lift** (`box-shadow: 0 1px 2px rgba(17,17,16,0.04), 0 1px 3px rgba(17,17,16,0.06)`; dark: `0 1px 2px rgba(0,0,0,0.4)`): cards, project tiles and the active nav item, which reads as a paper chip raised out of the sidebar.
- **Overlay** (`box-shadow: 0 8px 24px rgba(17,17,16,0.12), 0 2px 6px rgba(17,17,16,0.08)`; dark: `0 12px 32px rgba(0,0,0,0.5), 0 2px 8px rgba(0,0,0,0.4)`): elements that float over content, namely the open drawer and the focused skip link.

### Named Rules
**The Two Levels Rule.** Resting surfaces get the resting lift and floating layers get the overlay. There is no third level, and hover does not raise elevation. Hover changes border colour or background tint instead.

## Shapes

Corners are gently rounded and come in two sizes. Controls (buttons, inputs, nav links, code blocks, the error banner, the skip link) use 6px. Containers (cards, project tiles) use 10px. Badges are full pills (999px) and status dots are 8px circles. Borders are 1px translucent hairlines, never heavier. The focus ring is a 2px accent outline offset 2px (offset 0 on text fields).

## Components

### Buttons
Quiet by default. Only one action in a group is filled.
- **Shape:** gently rounded (6px), 34px minimum height (44px on coarse pointers), 6px 10px padding, weight 500, with 6px between icon and label.
- **Default:** Paper fill, Ink text, Hairline Strong border. Hover applies the Hover Strong wash.
- **Primary:** Button Blue fill with white text and no visible border. Hover goes to the deeper fill. There is one primary per form or action group.
- **Danger:** Failed Red fill with white text. It appears only as the confirm step of an in-place destructive confirmation, never as a first-click trigger.
- **Ghost:** transparent fill and border. Used for icon-only controls (menu, close) and the sidebar footer action.
- **Disabled:** 55% opacity with a default cursor.
- **Motion:** 120ms ease-out on background and border colour, removed under reduced motion.

### Destructive Confirmation (signature)
A destructive action never runs on the first click. The trigger is a default button. Clicking it swaps in place for a group with three parts: a one-sentence consequence ("what stops working"), a Danger confirm button that takes focus, and a default Cancel. Cancel or Escape backs out and returns focus to the trigger. There is no modal.

### Status Dot and Badges
- **Status dot:** a 10px mark in the status hue with a shape of its own: circle for passed, triangle for failed, square for errored, ring for skipped. It is `aria-hidden` and always followed by its word or count label ("3 failed").
- **Run verdict badge** (`RunStatusBadge`): icon and word, *Passed*, *Failed* or *Errored* (failures first, then errors). Overview, the runs list and any run summary use this one component; `note` appends text ("Passed · 2 quarantined").
- **Badge:** a Paper pill with a Hairline border, 12.5px/600, holding a 14px lucide icon and a word. *Passed* has Ink text with a green icon. *Failed* has Danger Text and a border at 40% of the failed red.

### Run Strip
A compact visual history of a test across recent runs, as a minimum 24px-tall link to the newest run. The strip holds one 6×18px bar per run with a 2px gap, oldest on the left.

- **Link:** the only keyboard-focusable element, its accessible name reads "Last 10 runs: 7 passed, 2 failed, 1 re-run, opens run #435". The summary counts every status, including "not run". It goes to the newest run the test was in (the last non-null status). Bars are `aria-hidden`.
- **Bars** are non-interactive spans with hover tooltips. Colours signal the last attempt's outcome in that run:
  - **Passed:** `--status-passed` (green).
  - **Failed:** `--status-failed` (red) with a notch cut from the top to signal failure without colour alone.
  - **Re-run:** `--status-rerun` (amber: #b07800 light, #e0a000 dark) with diagonal stripes to distinguish it without relying on hue (dark stripe tone #8a6200, 3.2:1 on the surface).
  - **Skipped:** a dashed outline with no fill, since the test did not run.
  - **Not in run:** a solid hairline outline in `--text-muted` (3.6:1 light, 4.9:1 dark) with no fill.
  - Each bar colour meets at least 3:1 non-text contrast against the cell's background in both themes.
- **WCAG:** the notch, stripes and outlines satisfy 1.4.1 (use of colour); the single 24px-tall link satisfies 2.5.8 (target size).
- **Accessibility:** a visually-hidden ordered list of all runs and their statuses follows the link (screen readers announce "Last 10 runs: 7 passed, 2 failed, 1 re-run" then list each bar's details). When the test is in none of the runs, the strip has `role="img"` with the summary only. With zero runs in the project, the cell shows the muted text "No runs yet".
- **Rendering:** until data arrives, the column shows 10 outlined skeleton bars (`--surface-2` fill, `--border-strong` outline). If the request fails, a dash appears and the rest of the page continues working.
- **Column placement:** "Last runs" goes after Title as `hide-narrow`, hidden at 640px and below. A legend above the table explains the colours and shapes. It is hidden when no case on the page is linked. An unlinked case shows only the text "not linked", with no empty strip.

### Run from QEOS
Starting a GitHub Actions run from the cases, and watching it end.

- **Play:** a Primary button with the Play icon ("Run", "Run selected (n)", "Run suite"). When disabled, the reason sits beside it in Graphite text, linked when Settings can fix it.
- **Confirmation:** an inline, non-modal card with `role="dialog"` that lists up to 10 cases then "+n more", `repo @ branch`, and the amber `.warn-note` "Tests may create real bookings in staging". For a suite with manual cases the title reads "Run n automated cases (m manual cases skipped)?" and lists only the automated ones. Focus goes to Cancel, Escape backs out, and Run reads "Starting…" and ignores a second click.
- **Selection bar:** sticky at the bottom of the list, with checkboxes on imported rows for editors only. A 200-case cap disables the remaining boxes. The select-all box is indeterminate while only some of the page is selected.
- **Run panel:** a card with `role="status"`. It has one state line with an 18px lucide icon whose shape differs per state (clock, spinning loader, check, cross, slash, alert), with colours from tokens, so state never rests on colour alone. The spin stops under reduced motion. It has "View in GitHub". Stop uses the Destructive Confirmation pattern ("Stop this run?" then "Stop run"), then "Stopping…", then "Stopped by <name>". When a run ends while Stop is answered, the panel quietly shows the final state. The results line appears only for a run that completed on GitHub: "Waiting for results…", or a link to the results, or after 5 minutes "Results not received: check the QEOS upload step". A completed run whose conclusion is skipped reads "Skipped" with the slash icon and the Stone tone, since it did not run. When the server holds an `error` for the request, the panel shows it: under the state line as a muted line on an active request ("GitHub: token invalid or expired"), and in the state text of a cancelled row ("Cancelled: The run is no longer on GitHub"). The Requested runs tab shows the same line under the status. The elapsed time on a running request is `aria-hidden`, and a visually hidden line states the status and changes only when the status does, so a screen reader is not interrupted every second. An ended run stays for 60 minutes after it ended (the later of `stopped_at` and `checked_at`), however long it ran. The panel re-reads the clock every 30 s, so that message appears without any other update, and not at all while there is no request.
- **Token expiry:** the amber `.warn-note` for owners and admins, from 14 days before expiry, inside a `role="status"` region that is always present so a change is announced. An expired token reads "Expired on <date>" in the Settings connection line, never "Connected".
- **Requested runs:** a tab beside Runs (route `runs/requested`) listing every Play with who requested it, the case count, the status, who stopped it, and links to GitHub and to the results.

### Cards / Containers
- **Corner Style:** 10px.
- **Background:** Paper on the Mist Page.
- **Shadow Strategy:** resting lift (see Elevation & Depth).
- **Border:** 1px Hairline.
- **Internal Padding:** 24px, or 16px under 640px and inside tile grids.
- **Anatomy:** an optional head row (title left, badge or action right), body, and a foot pinned to the bottom (`margin-top: auto`) that holds the one-click "go deeper" link.
- A card that holds a data table scrolls horizontally inside itself.

### Sortable Headers
`SortableTh` puts a button inside the `th`. The `th` carries `aria-sort` (`ascending`, `descending`, or `none`; absent state is `none`), and the button shows an arrow: a double chevron when idle, an up or down arrow on the sorted column. Clicking the sorted column flips it; another column starts descending for figures and dates, ascending for names. The sort lives in the URL as `sort` and `dir` (`lib/sort.ts`, defaults left out), so reload, share and Back keep it. Sorting happens on the server when the API has a sort parameter for that column (Tests: failures, duration, name), otherwise on the rows already loaded, and the page says so ("Sorted within these 50 rows"). Missing values always sort last.

### Narrow Meta
Columns that phones drop (`hide-narrow`) come back as a muted second line in the row's first cell (`NarrowMeta`: label in 600 weight, then the value). It is `display: none` above 640px, so a value is never read twice. Use it on every table that hides columns: Runs (status first), Tests, Flaky, Branches, Compare, Report, Requested runs, the import plan and Cases. Where a column is a graphic (the Cases run strip) the line carries a count instead ("1 failed, 2 passed of the last 3").

### Chart Textures
Outcome series are never told apart by hue alone. `ChartPatternDefs` defines the fills once per page: passed is solid, failed is diagonal stripes, errored is dots, skipped is thin lines, drawn in the surface colour over the status colour. The chart bars and the legend swatches point at the same ids. Comparison lines differ by dash (the second line is dashed) and carry point markers.

Each chart is a `figure` with an off-screen caption that states the totals and the notable point, uses Recharts' `accessibilityLayer` (arrow keys step through the tooltip) and has no `role="img"`. Below it a native `details` (`DataTableDisclosure`, "Show data table") holds the full series as a table. The legend (`SeriesLegend`) is a row of toggle buttons (`aria-pressed`): a hidden series is struck through. Titles, captions, column headings and the last-value tile name the granularity (day, week, month); X ticks are short `Intl` dates ("Mar 4"), thinned on narrow screens; tick text is Graphite, not Tick Grey.

### Secret Block
A value the server shows once (API key, invitation link, recovery codes) sits in a `SecretBlock`: Sidebar Mist fill, Hairline Strong border, a bold one-line note saying it cannot be shown again, the value in mono (wraps anywhere), and a Copy button whose result ("Copied") is announced politely. Recovery codes add Download and an "I saved these codes" button that dismisses them; the codes are not hidden until the reader says so.

### Data Tables
Rows are separated by Rule lines, with no zebra striping and no vertical lines. Headers are Graphite at 12.5px/600 and never wrap. Cells use 10px 12px padding and are top-aligned. Hovering a row applies the Hover wash. Numbers are tabular.

### Inputs / Fields
- **Style:** Paper fill, Hairline Strong border, 6px radius, 34px height (44px on coarse pointers). Labels stack above the field at 13px/500 in Graphite.
- **Hover:** the border darkens to Tick Grey.
- **Focus:** the border turns Signal Indigo, with a 2px accent outline at offset 0.
- **Filter dropdown:** a filter dropdown with more than 15 options is a searchable list (`FilterSelect`): a search field at the top of the open list, matching anywhere and ignoring accents, with an "x of y" count. Up to 15 options stay a native select.
- **Folder dropdown:** the folder filter (`FolderSelect`) looks like the other filters; its popup is a dialog with a search box, an "x of y" count and the folder tree. Searching keeps matching folders and their ancestors, Enter picks the first match, Esc and Tab close it, and picking applies at once.
- **Text field** (`TextField`): label, input, hint and error as one block. The error appears under the field when it is left (not while typing), is linked with `aria-describedby`, sets `aria-invalid`, and is never inside the `<label>`. A password field has a Show/Hide toggle (an eye icon with off-screen text, `aria-pressed`) outside the label. Checkboxes are drawn 18px (24px when they are a row's only target, in a table cell) with the Control Edge border; a label around one is the hit area.
- **Public pages** (`AuthShell`): the QEOS name and subtitle are a lockup paragraph; each page has its own h1 ("Sign in", "Create account", "Reset your password").
- **One primary:** each view has one primary button. A dirty form's Save takes it from Run; Run on a selection takes it from New case; Import takes it from Preview once there is a plan.
- **Inline form:** a one-row create form of label and input pairs ending in its submit and Cancel buttons. It wraps on narrow widths.

### Navigation
- **Sidebar:** Sidebar Mist with a right hairline. From top to bottom it holds the brand (lucide mark in Signal Indigo with the bold 15px wordmark), the project switcher (a native select grouped by organization), project views, workspace links, and a footer pinned to the bottom with Security and Sign out.
- **Nav link:** Graphite text at weight 500 with a 17px lucide icon, 34px tall and 6px radius. Hover applies Hover Strong with Ink text. **Active** is a Paper chip with resting lift, Ink text and a Signal Indigo icon.
- **Section title:** 12px/600 Graphite, sentence case. It is a real group label such as "Workspace".
- **Mobile (900px and below):** a sticky top bar holds a ghost menu button and the brand. The drawer slides in over 200ms `cubic-bezier(0.2, 0, 0, 1)`. Opening it focuses the first control inside. Escape, the backdrop, the close button or following a link closes it, and focus returns to the menu button.

### Project Tile
A Paper tile with a 10px radius, Hairline border and resting lift, holding a folder icon and the project name at 600. On hover the border turns Signal Indigo, with no lift and no underline.

### Error Banner
A 6px-radius box with a Danger Text border and text over a 6% failed-red tint, with an optional Retry button. It uses `role="alert"`. Loading and empty states are plain Graphite sentences that say what is absent and how data arrives. They never show a zero in place of missing data.

### Code Block
Mist Page fill, Hairline border, 6px radius, 12px padding, 13px mono, and horizontal scroll. It is used for copyable CI snippets. An expanded failure message inside a table cell is mono 12.5px with preserved line breaks and no box. A read-only Gherkin block colours keywords, tags, tables, doc strings and comments, plus step values: quoted "values" use `--gk-string` and `<placeholders>` use `--gk-param` on a light tint of `--gk-param-bg`; each meets 4.5:1 on Sidebar Mist in both themes.

### Accessibility Plumbing
- A **skip link** stays hidden until focused, then appears top-left as a Paper chip with the overlay shadow.
- **Route focus:** on each user navigation (not the first render, not redirects), focus moves to the view's content region, which is the project tab panel or `<main>`. Regions take focus without a visible ring; the ring belongs to controls.
- **Titles:** each view sets `document.title` as "View · Project · QEOS".
- **Focus not obscured:** a bar stuck to the bottom of the viewport (the Cases selection bar) writes its height to the page's `scroll-padding-bottom` while it exists and pads the table, so a row reached by keyboard scrolls above it.
- **Drawer:** on narrow screens the open sidebar is a modal dialog (focus trapped, Escape from anywhere closes it). Following a link in it hands focus to the new page's content, not back to the menu button. Widening the window past the breakpoint closes it and removes the dialog role.
- **Live regions:** a status card announces only its status line (`role="status"` on that line), never the links and buttons around it.

## Do's and Don'ts

### Do:
- **Do** use `accent-text` for links and blue text and `accent-fill` behind white text. Keep `accent` for rings, icons, selection and hover borders.
- **Do** use `text-secondary` for all readable secondary copy. Use `text-muted` only for chart axis ticks.
- **Do** pair every status hue with its word, count or legend.
- **Do** use `danger-text` for error copy and the failed-red fill only for the confirm step of a destructive action.
- **Do** take icons from lucide-react only, sized 14 to 20px and `aria-hidden="true"`, beside visible text or inside a control with an `aria-label`.
- **Do** give every interactive control a 44px minimum under `pointer: coarse` and keep 16px body text under 640px.
- **Do** compute any new text pair in both themes before shipping. It must be 4.5:1 or better.
- **Do** confirm destructive actions in place, with the consequence stated in one sentence and focus moved to the confirm button.
- **Do** give each view a `document.title` and move focus to its content on navigation.
- **Do** put the one-click "go deeper" link in a card's foot.

### Don't:
- **Don't** use green, red, orange or skipped-stone for anything that is not a test outcome, error or destruction.
- **Don't** set body or link text in `accent` or `status-failed`, because neither reaches AA as text on every surface.
- **Don't** add a third shadow level, raise elevation on hover, or use hard offset shadows.
- **Don't** use icons from any other set, emoji or Unicode glyphs as icons, or an icon without a text label.
- **Don't** add a manual theme toggle or a light-only colour. Every token needs a dark counterpart or a reason it holds in both themes.
- **Don't** show zero, a placeholder number or sample data where the API returned nothing. Show the absence.
