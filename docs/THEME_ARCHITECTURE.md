# Theme architecture consistency audit

Covers Botanical, Dark Romance, Digital Chrome, and Pink Pop as they exist in the code today.

## The good news first: this is a real, working token system

Every theme (`body.theme-pop`/`theme-forest`/`theme-botanical`/`theme-berry`) defines the exact
same contract of CSS custom properties — `--board`, `--accent`, `--paper`, `--paper2`, `--ink`,
`--ink-dim`, `--plum`/`--moss`/`--sky`/`--rose`/`--coral`/`--lime`/`--bubble`/`--gold` (each with
a `-soft` variant), `--black`, `--line`, `--danger`, `--theme-photo-bg`, and 6 font roles
(`--font-xl`, `--font-l`, `--font-accent`, `--font-ui`, `--font-mono`, `--font-hand`) — with a
separate `.appearance-dark` block re-defining the same names for dark mode. Every component's
CSS reads these var names and **never** a theme name or a hardcoded color directly. That means:

- **Adding a 5th theme needs zero changes to any screen's component CSS.** It's purely additive:
  one new `body.theme-X{}` block (+ `.appearance-dark` variant, + the six `bg-ctx-*` background
  rules, + the glass-card treatment block), four new entries in the JS lookup tables below, and a
  new row in the `THEMES` array. Nothing else in the ~4600 lines of JS or the rest of the CSS
  needs to know a 5th theme exists.
- **Digital Chrome proves the contract is genuinely abstract, not just "4 copies of the same
  idea."** Berry defines its own richer internal font-role names (`--font-display`,
  `--font-editorial`, `--font-label`, `--font-accent-ui`, `--font-slab`, `--font-playful`,
  `--font-data`) and then maps them onto the shared 6-name contract
  (`--font-xl: var(--font-display); --font-l: var(--font-editorial); ...`). A theme with a
  completely different internal naming philosophy still slots into the same contract without
  touching a single component.

## Per-theme JS lookup tables (the non-CSS half of the contract)

Theme-specific *behavior* (not just color) is centralized the same way, each keyed by the same
4 theme ids:

| Table | Purpose |
|---|---|
| `THEME_WIDGET_ICONS` | which emoji represents each widget (Water, Tasks, …) per theme |
| `THEME_MOOD_FACES` | the 5-step mood slider's icon sequence per theme |
| `THEME_TASK_MOODS` | the 16-option task-sticker picker's icon set per theme |
| `THEME_DAY_COLORS` | the weekday accent-color rotation per theme (exists specifically so a shared "Monday = red" default can't leak a wrong color into a theme that shouldn't have literal red) |
| `THEME_TASK_MOOD_DEFAULT` | the single default icon shown on an empty task-mood button per theme |

Same story as the CSS contract: a 5th theme adds one entry to each table; nothing that *reads*
these tables needs to change.

## Known inconsistency: sticker pack ids don't match current theme names

The 4 built-in decorative sticker packs (placed on Date View pages, a separate system from the
per-theme task-mood icons above) are stored under
`assets/stickers/{digital-chrome, y2k-vixen, dark-romance, petal-botanical}/`, and referenced
internally by those exact folder names (`BUILTIN_STICKER_PACKS[].id`). Two of those four predate
a later rename: the *theme* now called "Pink Pop" still has its sticker pack's internal id as
`y2k-vixen`, and "Botanical" (formerly "Petal") still has its pack folder as `petal-botanical`.

- **User-visible impact, fixed in this pass:** the Sticker Sheet's tab label for the Pink Pop
  pack read "Y2K Vixen" instead of "Pink Pop" — this was a plain display-string bug (the label
  text shown to users), safe to fix without touching any stored data, so it's fixed now.
- **What's deliberately *not* touched, and why:** the internal folder names/ids
  (`y2k-vixen`, `petal-botanical`) still don't match current theme names. Renaming them would
  mean moving files and changing the id strings baked into `BUILTIN_STICKER_INDEX` keys
  (`"b:<packId>:<fileName>"`) — and any user who has **already placed** one of those stickers on
  a day has that exact string saved in their `wp-stickerzones-v5` data (see Data Contracts). A
  silent id rename would make their already-placed stickers stop resolving (the image would just
  disappear). This is exactly the kind of "looks safe, actually touches live user data" trap this
  preparation pass was told to avoid — if it's ever worth cleaning up, it needs a real one-time
  data migration (rewrite every `sid` referencing the old id to the new one, for every existing
  user), not just a find-and-replace in the code.

## Known inconsistency: decorative sticker packs aren't tied to the active theme

The Sticker Sheet lets a user pick *any* of the 4 built-in packs regardless of which theme is
currently active — a user on Dark Romance can freely place Digital Chrome stickers. This may well
be intentional (creative freedom, not everyone wants their stickers locked to their theme), but
it's worth a deliberate decision rather than leaving it as an unexamined default, since the pack
names strongly imply a per-theme pairing. Not a bug — a product decision to make, not code to fix.

## Duplicated (but not wasteful-for-no-reason) CSS: the glass-card treatment

Each of the 4 themes has its own "give these ~15-20 card selectors a frosted-glass treatment"
CSS block (`backdrop-filter: blur(...) saturate(...)`, plus border/radius/shadow rules), written
out per theme rather than factored into one shared selector list with only the blur/shadow
*values* varying by theme. This is real duplication (the selector list — `.note`,
`.myspace-card-shell`, `.budget-hero-stat`, `.day-widget-cell`, `.wide-block`, etc. — repeats
near-verbatim 4 times), but it's not accidental waste: Digital Chrome's dark/light variants layer
on genuinely extra detail (multiple inset-shadow "light source" layers) the other three don't
have, so a naive "one shared block + a variable" refactor would either have to grow that block to
Digital Chrome's complexity for every theme, or special-case Digital Chrome anyway. **Describing
this, not fixing it** — collapsing it safely would mean touching visual CSS across all 4 themes
at once, which is real redesign risk for a purely internal tidiness win. Worth doing deliberately,
with full visual regression screenshots, if it's ever revisited — not as an incidental cleanup.

## Assets

- **Backgrounds:** not files — base64 WebP images embedded directly in each theme's CSS
  `--theme-photo-bg` values (this is also the main reason `index.html` is 3.6&nbsp;MB).
- **Stickers, avatars, app icons:** real files under `/assets/` and the repo root, referenced by
  relative path — these load like any other static asset and need no special handling to reuse in
  an iOS build.
- Nothing found hardcodes a raw hex color for anything that should have been theme-aware. The few
  raw hex colors that do exist in component CSS (e.g. a fixed green for income amounts, a fixed
  red for negative balances) are semantic status colors used identically across all 4 themes —
  that's a correct, deliberate choice (a negative balance should always read as recognizably "bad"
  regardless of theme), not an inconsistency.

## Third issue found and fixed: `currentTheme` could desync from the applied CSS class

`applyTheme(key)` only ever toggled the body's `theme-*` class — it never touched the module-level
`currentTheme` variable that every per-theme *JS* lookup table reads (`THEME_DAY_COLORS`,
`THEME_MOOD_FACES`, `THEME_TASK_MOODS`, `THEME_WIDGET_ICONS`, `THEME_TASK_MOOD_DEFAULT`, plus
`moodFace()`/`widgetIcon()`/`currentTaskMoods()` which read it directly). `currentTheme` itself
was set in exactly two places: the very first, pre-login line (`localLoad('wp-theme-v5','berry')`,
a synchronous LOCAL-only guess) and `setTheme()` (called only from Settings/Year-view UI). The
post-login reconciliation in `onSignedIn()` — `applyTheme(load('wp-theme-v5', currentTheme))` —
re-resolved the theme from the *cloud* value and reapplied the CSS class, but passed the result
straight to `applyTheme()` without also assigning it back to `currentTheme`. On a browser whose
local pre-login guess differed from the account's actual (cloud) theme, this left the body class
and `currentTheme` pointing at two different themes for the rest of the session: every
CSS-token-driven color (background, cards, buttons) correctly showed the real theme, while every
JS-lookup-driven color (a day's own weekday accent, mood face, task-mood icon set) silently kept
computing from the stale local guess instead — the exact "leftover color from the previous theme"
symptom, and why it needed a real cross-device mismatch to reproduce rather than showing up on
simple in-app switching (which always goes through `setTheme()`, already correct). Fixed by
reassigning `currentTheme = load('wp-theme-v5', currentTheme)` before calling `applyTheme()` in
that one call site.

## Two small palette adjustments (not a redesign)

- **Digital Chrome's `--accent`/`--rose`** (previously the same bright sky-blue, `#4d7dff` light /
  `#7fb2ff` dark, in both slots) were deepened to a calmer navy-indigo (light, `#3d4f95`) and soft
  lavender-blue (dark, `#8b93d9`), per explicit design feedback that the original read as loud
  "standard UI blue" rather than premium. Every other token in the theme (backgrounds, decorative
  gradients, `--sky`/`--plum`/`--bubble`, the `DAY_COLORS_BERRY` weekday rotation) is untouched.
- **Dark Romance's primary display font** was `'Cormorant Garamond'` (`--font-xl`/`-l`/`-accent`/
  `-hand`) — at the large display sizes and bold weights this app uses those roles for, its
  delicate old-style curves read as thin/dated rather than romantic. Switched to `'Fraunces'`,
  the same contemporary display serif Botanical and Digital Chrome already use elsewhere in the
  app (an existing typographic choice being reused, not a new font introduced), keeping Cormorant
  Garamond only as a fallback — matching Botanical's own font-stack pattern.

## Summary

The theme system itself is sound and genuinely extensible — this is one of the stronger parts of
the codebase, not a liability for iOS. Of the issues found across passes: two were cosmetic labels
(now fixed), one is a documented, deliberately-untouched internal naming mismatch that would need
a real data migration to clean up safely, and one (`currentTheme` desync after a cross-device
theme change) was a genuine functional bug, now fixed. Nothing here blocks iOS work.
