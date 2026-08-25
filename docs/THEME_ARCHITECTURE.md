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

## Summary

The theme system itself is sound and genuinely extensible — this is one of the stronger parts of
the codebase, not a liability for iOS. The two issues found are a (now-fixed) cosmetic label and
a documented, deliberately-untouched internal naming mismatch that would need a real data
migration to clean up safely. Neither blocks iOS work or needs attention before it.
