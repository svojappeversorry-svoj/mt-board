# Data contracts: `app_data.data_key` → payload shape

This is a from-the-code inventory of every `data_key` the Web app reads or writes, what its
`data` JSON actually looks like today, and how it's read/written. It exists so a future iOS
client can read and write the *exact* same shapes without guessing — nothing here was
redesigned; it's a transcription of `index.html` as it stands.

**Re-verified against the code on 2026-08-25.** Four small discrepancies from the first pass
of this document were found and corrected (nothing in the *app* changed, only the doc):
`wp-photos-v1` was missing its 20-photos-per-day limit and the note that `caption`/`event`/
`favorite`/`location`/`tags` have no UI yet; the built-in `steps` widget's `kind` was
mis-described as implicit when it's actually declared explicitly (`kind:'number'`); and
`wp-expense-currencies-v1` was missing the note that only 5 currency codes are actually
selectable through the UI today. See the relevant sections below for details.

## How storage actually works (applies to every key below)

Every key goes through two functions defined near the top of the app's `<script>`:

```js
function save(key, val){
  localSave(key, val);                 // always: localStorage.setItem(key, JSON.stringify(val))
  cloudCache[key] = val;
  if(!currentUserId || !sb) return;    // signed out / offline mode: local-only, stop here
  // ...debounced ~600ms...
  sb.from('app_data').upsert(
    { user_id: currentUserId, data_key: key, data: val, updated_at: new Date().toISOString() },
    { onConflict: 'user_id,data_key' }
  );
}
function load(key, fallback){
  if(currentUserId && key in cloudCache) return cloudCache[key];
  return localLoad(key, fallback);     // localStorage, JSON.parse'd
}
```

Consequences that apply to **every** key documented below, so they're not repeated per key:

- **The whole value is replaced on every write.** There is no partial/field-level update —
  `save('wp-days-v5', daysData)` re-uploads the entire `daysData` object even if only one field
  of one day changed. An iOS client should follow the same read-modify-write-whole-object
  pattern, not try to patch individual fields server-side.
- **Cloud is only fetched once per session**, at sign-in (`fetchAllCloudData()` — one
  `select` for every row belonging to that `user_id`, cached in memory as `cloudCache`). Nothing
  re-fetches mid-session. See the iOS audit for what this means for Web↔iOS live sync.
- **`localStorage` is always written too**, even when signed in — it's the offline fallback and
  what "Continue offline" mode runs on entirely.
- **`data_key` is the literal string, including any suffix** — e.g. `wp-month-goals-v1-2026-08`
  is one specific row, not a template evaluated server-side. Keys marked "per month" or
  "per currency" below produce one row per concrete value.
- **The `-v5`/`-v1` etc. suffix is just a generation label the app never parses** — it's there so
  a genuinely incompatible future redesign of a key's shape could ship as e.g. `wp-days-v6`
  without touching old data. None of the current keys have logic keyed off their own version
  number; don't invent meaning that isn't there.

### The four keys with special first-sign-in merge behavior

`wp-days-v5`, `wp-photos-v1`, `wp-widget-daily-v1`, and `wp-expenses-v1` get merged (not
overwritten) the *first* time a browser that already has local data signs into an account that
already has cloud history — so offline-recorded data isn't silently discarded. This merge is
gated by a **local, one-time flag** (`wp-cloud-migrated-v1`, plain `localStorage`, never synced)
so it only ever runs once per browser; every sign-in after that treats the cloud copy as
authoritative, so deletions actually stick. A future iOS "first sign-in merge" should replicate
this once-only gating — merging every single time would resurrect anything ever deleted on
another device.

---

## Key-by-key reference

### `wp-theme-v5`
- **Purpose:** which of the 4 visual themes is active.
- **Shape:** a single string: `"pop" | "forest" | "botanical" | "berry"`.
- **Default:** `"berry"` (Digital Chrome) for a brand-new install. An existing value (including
  the legacy `"pop"` some old accounts still have) is never overridden.
- **Read:** once at page load, before any Supabase session is known, via raw `localStorage`
  (`localLoad`) so the very first paint already has the right theme; re-resolved via `load()`
  right after sign-in.
- **Write:** whenever the user changes theme (Settings dropdown, or once during onboarding).

### `wp-appearance-v1`
- **Purpose:** Light / Dark / follow-system preference.
- **Shape:** `"system" | "light" | "dark"`.
- **Default:** `"system"`.
- **Read:** at initial paint (localStorage only, same reasoning as theme) and again inside
  `buildApp()` once signed in.
- **Write:** Settings appearance dropdown; once during onboarding.

### `wp-user-name-v1`
- **Purpose:** display name.
- **Shape:** plain string. No length limit is enforced on read; the Settings input caps entry at
  40 characters (`maxlength="40"`) but that's a UI constraint, not a stored guarantee.
- **Default:** `""`.
- **Write:** Settings name field, on every keystroke (`input` event); once during onboarding.

### `wp-username-v1`
- **Purpose:** the public `@handle` used in Explore and on public moments instead of the real
  name above — see `journalAuthorName()`. Onboarding now requires claiming one (step 2 of the
  flow); existing accounts from before this feature can set one any time from My Profile.
- **Shape:** plain string, lowercase, no leading `@` (the app adds that only when displaying it),
  `^[a-z0-9_]{3,20}$`.
- **Default:** `""` — an account with no username yet shows as `"SVOJ member"` in public content,
  never the real name/email (see `docs/USERNAMES_TABLE.md`).
- **Write:** My Profile's Username field; once during onboarding.
- **Global uniqueness:** enforced by a separate, publicly-readable `usernames` Supabase table —
  same reasoning and same "required manual SQL step" caveat as `public_journal_moments` (see
  `docs/USERNAMES_TABLE.md`). This key stores the canonical value; the table exists only to
  answer "is this taken" and to let a stranger's client resolve who authored a public moment.

### `wp-avatar-v1`
- **Purpose:** chosen avatar character.
- **Shape:** string id from the 15-item `AVATAR_COLLECTION` (`"glamour-chihuahua"`,
  `"surf-budgie"`, `"cheeky-monkey"`, `"programmer-hamster"`, `"happy-duckling"`,
  `"fairy-horse"`, `"angel-piglet"`, `"gangster-cow"`, `"looksmax-koala"`,
  `"romantic-capybara"`, `"sigma-lion"`, `"explosion-cat"`, `"coquette-bunny"`,
  `"rage-squirrel"`, `"party-dolphin"`), or `""` if never chosen. Each id's artwork is a real
  PNG file under `assets/avatars/<id>.png` — already a self-contained circular badge (its own
  drawn border, transparent square canvas around it), shown at 1:1 inside a
  `border-radius:50%` clipping container with no zoom/crop.
- **Default:** `""`.
- **Write:** Settings avatar grid; once during onboarding (now **required** — onboarding's avatar
  step has no `skippable`/Skip affordance and its Next button stays disabled until one is picked;
  see `ONB_PAGES`'s `avatar` entry and `onbWireAvatar()` in `index.html`).
- **Replaced set (this pass):** the previous 10-item collection (`angel-pig`, `glam-cow`,
  `glam-dog`, `beach-bird`, `koala`, `chaotic-monkey`, `hamster-glasses`, `duck`,
  `capybara-rose`, and an earlier `fairy-horse` piece of art) was removed wholesale and its
  `.webp` files deleted. An account whose `wp-avatar-v1` still holds one of those old ids
  (other than `fairy-horse`, which the new collection reuses under the same id but with new
  artwork) simply gets `avatarById()` returning `null` for it — the app's existing "no avatar
  chosen" fallback (a plain face glyph) renders instead, same as any other orphaned id
  elsewhere in this codebase. Nothing crashes; the user just needs to pick again.

### `wp-onboarding-complete-v1`
- **Purpose:** whether the onboarding flow has run.
- **Shape:** boolean.
- **Default:** `false`.
- **Write:** set to `true` exactly once, at the end of onboarding.

### `wp-days-v5`
- **Purpose:** the core per-day record — mood, water, sleep, tasks, notes for that date. This is
  the single largest and most-written key in the app.
- **Shape:** an object keyed by `dateKey` (`"YYYY-MM-DD"`, local calendar date). Each value:

  | field      | type                                             | default   | notes |
  |------------|--------------------------------------------------|-----------|-------|
  | `mood`     | number, 0–4                                       | `2`       | slider value |
  | `water`    | number                                            | —         | **legacy** "glasses" count (0–8ish); no longer written by current code, kept only so old rows can be one-time-migrated into `waterMl` on first read |
  | `waterMl`  | number                                             | `0`       | current water tracker unit, millilitres |
  | `waterLog` | `number[]`                                        | `[]`      | each entry is one ml amount added, in order — powers "undo last" |
  | `sleep`    | number, 0–12, step 0.05                           | `7`       | hours |
  | `todos`    | `{ text: string, done: boolean, vibe: string }[]` | `[]`      | **no `id` field** — a todo is addressed only by its array index within that day; moving/toggling/deleting all operate on `todos[i]`. (This `vibe` field is the per-task mood sticker, unrelated to the removed "Today's Vibe" widget below — see `todo.vibe`/`currentTaskMoods()`.) |
  | `notes`    | string                                            | `""`      | free-text "what happened today" |

  A `vibes: string[]` field ("Today's Vibe" tags) used to live here too. The feature was removed
  entirely — the widget, its picker UI, the `VIBES`/`customVibes` data model, and
  `wp-vibes-custom-v1` are all gone. Any account with old day records still carrying a leftover
  `vibes` array on disk has that field silently ignored now (nothing reads or writes it); it is
  never stripped out on read, since deleting historical fields wasn't necessary to remove the
  feature.
- **Defaulting/migration on read:** `ensureDayData(key)` lazily creates a day record with the
  defaults above the first time it's touched, and backfills `waterLog`/`waterMl` onto *existing*
  day objects that predate those fields. **An iOS reader must apply the same defaulting** — older
  stored days are not guaranteed to already have every field present.
- **Read:** the entire object loaded once into memory at app start (`let daysData = load(...)`).
- **Write:** the entire `daysData` object is re-saved on *every* mutation — adding/checking off/
  deleting/moving a task, logging or undoing water, changing mood or sleep, or editing notes.
- **Merge-on-first-sign-in:** yes, per-date-key union (see above).

### `wp-photos-v1`
- **Purpose:** photos attached to specific days.
- **Shape:** object keyed by `dateKey`, each value an array of:

  | field       | type    | notes |
  |-------------|---------|-------|
  | `id`        | string  | `crypto.randomUUID()`, or a timestamp+random fallback string on very old browsers |
  | `date`      | string  | same `dateKey` as the outer object key |
  | `src`       | string  | a `data:` URL — the actual image bytes, base64, already resized/compressed client-side. **No Supabase Storage is used**; the image lives directly inside this JSON. |
  | `caption`   | string  | default `""` |
  | `event`     | string  | default `""` |
  | `favorite`  | boolean | default `false` |
  | `location`  | string  | default `""` |
  | `tags`      | `string[]` | default `[]` |
  | `createdAt` | number  | `Date.now()` at upload time |
  | `order`     | number  | position among that day's photos |

- **Limit:** at most 20 photos per day (`MAX_PHOTOS_PER_DAY`) — the add button disables past that.
- **Fields with no UI yet:** `caption`, `event`, `favorite`, `location`, and `tags` are part of the
  stored shape and initialized on every upload, but nothing in the current app reads or lets a
  user set them — there is no caption/tag editor anywhere today. Treat them as reserved for a
  future feature, not as data any existing screen depends on.
- **Write:** the whole array (for that day, inside the whole object) is re-saved on any add,
  edit, delete, or reorder.
- **Merge-on-first-sign-in:** yes, per-date-key union.

### `wp-journal-moments-v1`
- **Purpose:** the Journal tab's private moments — "things you found today worth keeping",
  each its own self-contained record (a day can have zero, one, or several). This **replaces**
  the earlier `wp-journal-v1` ("the Journal tab's timeline", a freeform mood/text diary) —
  that key is retired: the app no longer reads or writes it, and its shape doesn't map onto
  this one (diary entries vs. typed moments), so there is deliberately no migration between
  them. An account with old `wp-journal-v1` data simply has it become an inert, orphaned
  localStorage/`app_data` key — harmless, same as any other retired key elsewhere in this app.
- **Shape:** a flat array of:

  | field         | type              | notes |
  |---------------|-------------------|-------|
  | `id`          | string            | `crypto.randomUUID()`, or a timestamp+random fallback string |
  | `date`        | string            | `dateKey` (`YYYY-MM-DD`) the moment belongs to — the Journal date it was kept under, independent of `createdAt` |
  | `type`        | string            | one of `'photo' \| 'place' \| 'song' \| 'movie' \| 'recipe' \| 'link' \| 'note'` |
  | `title`       | string            | default `""` — optional for every type except place/song/movie/recipe, where it's that type's one required field |
  | `description` | string            | freeform, always optional, default `""` |
  | `image`       | string            | data URL, ~1000px/0.8 quality (`resizeImageJPEG`) — only ever set for `photo`, and optionally for `movie`/`recipe`; `""` otherwise. Only loaded into the DOM when the moment is actually opened, never in the list/card view |
  | `thumb`       | string            | data URL, ~220px/0.72 quality, generated from the same source file as `image` in one pass (`journalProcessPhoto()`) — this is what every list/card/Explore grid actually renders, so opening Journal never has to decode a full-size photo |
  | `externalUrl` | string            | data URL is never stored here — just the URL string itself, for `song`/`movie`/`recipe`/`link`/`photo`/`note` (required for `link`, optional otherwise). `photo` and `note` gained this field this pass (previously they had no link field at all) specifically so the public-visibility requirement below has something to check for every type. `""` if none. Only ever rendered as a clickable `href` through `journalSafeUrl()`, which strips anything that isn't a plain `http(s)` link |
  | `location`    | object \| `null`  | `place` only: `{ name: string, url: string }` (`url` optional — a pasted external map link, never map content itself). For `place`, this `url` (not `externalUrl`) is what the public-visibility link requirement checks — see `journalMomentLinkValue()` |
  | `artist`      | string            | `song` only, optional, default `""` |
  | `visibility`  | string            | `'private' \| 'public'` — **always starts `'private'`**; flipped only by the explicit Make Public/Make Private action, and only when `journalCanPublish(m)` passes: both a link (`externalUrl`, or `location.url` for `place`) and a non-empty `description` must be present. Saving privately has no such requirement — only going public gates on it. Editing an already-public moment down to missing either one automatically demotes it back to `'private'` (`journalBindMomentForm`'s save handler) rather than leaving an invalid public state |
  | `savedFrom`   | object \| `null`  | set only when this moment was copied in via Explore's "Save to My Journal": `{ momentId: string (the public row's id), author: string }` — provenance only, this copy is fully independent afterward |
  | `sourceUnavailable` | boolean     | `savedFrom`-only. `false` until `journalCheckSavedSource()` confirms the original public row is gone (the author made it private/deleted it), at which point `true` and every content field above (`title`/`description`/`image`/`thumb`/`externalUrl`/`location`/`artist`) is wiped to `''`/`null` — see "Revoking a saved copy" below |
  | `unavailableSince` | number \| `null` | `Date.now()` at the moment `sourceUnavailable` flipped to `true`; `null` otherwise. Drives the 48-hour auto-removal below |
  | `createdAt`   | number            | `Date.now()` at save time; also the ordering key for moments on the same `date` |
  | `updatedAt`   | number            | bumped on every edit or visibility change |
  | `publishedAt` | number \| `null`  | `Date.now()` when last made public, `null` while private — this is what Explore sorts by |

- **Default:** `[]`.
- **Write:** the whole array is re-saved on every add, edit, delete, or visibility change —
  same pattern as `wp-photos-v1`/`wp-expenses-v1`, no partial-row updates.
- **Merge-on-first-sign-in:** **no** — not one of the four keys with special merge behavior
  (see above); same caveat as `wp-journal-v1` had.
- **Image pipeline:** `journalProcessPhoto(file)` resizes the source file twice in one pass
  (`resizeImageJPEG(file, 1000, 0.8)` for `image`, `resizeImageJPEG(file, 220, 0.72)` for
  `thumb`) — the existing pipeline every other photo feature in this app already uses, just
  called twice so lists never have to load the bigger copy.
- **Public/Explore counterpart:** when a moment's `visibility` is `'public'`, a matching row is
  additionally upserted into a **separate** Supabase table, `public_journal_moments` — `app_data`
  cannot be used for this because its row-level security is strictly "owner reads/writes their
  own row only" (see docs/SUPABASE_ENVIRONMENTS.md), so no row there can ever be visible to
  another signed-in user. See **docs/JOURNAL_PUBLIC_TABLE.md** for the table's exact shape, the
  SQL to create it, and why this session cannot run that SQL for you. Until that table exists in
  your Supabase project, Make Public/Explore/Save-to-My-Journal are inert no-ops (fail silently,
  logged to the console) — every private Journal feature above works today regardless.
- **`author` field (on the public row, not this key):** now the publisher's `@username`
  (`journalAuthorName()`, see `wp-username-v1` above) instead of the real name/email prefix it
  used to snapshot — never the real name for anything public. Rows published before this change
  keep their old snapshotted value (not retroactively rewritten); see
  `docs/USERNAMES_TABLE.md`.
- **Shareable public URL:** a public moment's own `id` (this key's `id` field, same value as the
  public row's primary key) doubles as its shareable link's slug — `?moment=<id>`, resolved by
  `renderPublicMomentView()` near the top of `index.html` (before `buildApp()`/sign-in, so it
  works for a signed-out visitor). "Copy link"/"Share" (Explore, and a moment's own detail view
  when public) just builds this URL client-side (`publicMomentUrl(id)`) — no server-issued token.
  See docs/JOURNAL_PUBLIC_TABLE.md's "Shareable public URL" section.
- **Revoking a saved copy:** Make Private must actually revoke access, including from anyone who
  already ran "Save to My Journal" on it — not just remove it from *future* Explore visitors.
  `journalCheckSavedSource(m)` re-checks (by id, against `public_journal_moments`) every time a
  `savedFrom` moment is actually rendered — opening Journal, or opening that moment's own detail
  — whether its source still exists. A "still public" result is deliberately **not** cached past
  that single check (only concurrent duplicate in-flight requests for the same id are
  suppressed), so a later revocation is always eventually noticed the next time the moment is
  viewed. Once confirmed gone, the local copy's content is wiped (see `sourceUnavailable` above)
  and the card/detail show a plain "no longer available" placeholder instead of silently
  deleting the entry (which would look like a bug to whoever saved it) or leaving a full
  independent copy forever (which would defeat the author's Make Private). `journalMomentCardHtml()`/
  `journalOpenMomentDetail()` special-case `sourceUnavailable` to render that placeholder; the
  only action left on it is Delete. 48 hours after `unavailableSince`,
  `journalPruneExpiredUnavailable()` (run on every sanitize pass and every `buildJournalDayView()`)
  removes the entry outright, so a dead placeholder never lingers indefinitely either.
- **Calendar navigation:** the 📅 button next to the date opens the app's own Month view
  (`showMonthView(monthIdx, year, pickCallback)`) in a trimmed "pick mode" — a module-level
  `monthViewPickCallback` set only for this call — showing just the header/weekday row/day grid
  (no Goals/Expenses/Favorites/Notes sections) with a "← Journal" link back out, instead of a
  browser-native `<input type="date">` popup. Tapping a day calls the callback straight back into
  Journal on that date; every other way of reaching Month view (the My Space "calendar" widget,
  a Year-view month tile) passes no callback and behaves exactly as it always did — pick mode is
  never left dangling across unrelated navigation since `showMonthView()` always resets
  `monthViewPickCallback` explicitly on entry, never leaves it from a previous call.

### `wp-widget-config-v1`
- **Purpose:** which optional widgets appear on the **My Day** detail page, in what order, plus
  any user-defined custom widgets. (Separate from My Space's own layout — key below.)
- **Shape:**
  ```
  {
    enabled: string[],       // ordered widget ids, e.g. ['mood','water','sleep','tasks','notes']
                              // ids are either built-in ("mood","water","sleep","steps","tasks",
                              // "notes","photos", or one of the 7 Journal-bridge ids below) or a
                              // custom widget's own id (format "custom:<timestamp><random>")
    customWidgets: {
      id: string,             // "custom:<timestamp><random>"
      name: string,
      description: string,
      type: "text" | "checklist" | "number" | "counter" | "rating" | "toggle" | "scale" | "timer"
    }[]
  }
  ```
- **Default:** `{ enabled:['mood','water','sleep','tasks','notes'], customWidgets:[] }`.
- **Limits enforced client-side (not in the stored data):** at most 10 built-in widgets enabled
  at once, at most 3 custom widgets total.
- **Mandatory ids:** `"tasks"` and `"mood"` (`MANDATORY_WIDGET_IDS`) can never be removed — their
  remove button is hidden (shows "required" instead) and `removeWidgetFromPage()` no-ops for
  them defensively. `sanitizeWidgetConfig()` also re-adds either one to `enabled` if it's ever
  found missing (e.g. an account whose data predates this rule), so it self-heals rather than
  requiring a one-time migration.
- **Journal-bridge ids** (`kind:'journalMoment'`): `momentPhoto`, `momentPlace`, `momentSong`,
  `momentMovie`, `momentRecipe`, `momentLink`, `momentNote` — one per Journal moment type. These
  have **no storage of their own** in `wp-widget-daily-v1` below; they read/write straight into
  `wp-journal-moments-v1` (filtered by date + type), so a moment created from a My Day widget is
  the exact same record Journal itself shows — never a duplicate. See `genericWidgetHtml`'s
  `'journalMoment'` branch and `journalOpenMomentForm()` in `index.html`.
- **Removed built-in widgets (this pass):** `gratitude`, `dailyHighlight`, `freeText`, `music`,
  `movie` (the old generic Entertainment one — distinct from the new `momentMovie` Journal-bridge
  widget above), and `favoriteThing`. Same self-healing as the `"vibes"` removal below — any
  account with one of these still in a saved `enabled` array has it silently dropped on next load.
- **`steps`'s `kind` changed** from `'number'` (manual entry) to `'healthSteps'` — it no longer
  accepts typed-in values at all; see the `wp-widget-daily-v1` entry below and
  `docs/IOS_READINESS.md`'s Steps/HealthKit section for the full architecture.
- **Known display-only exception:** the dedicated My Day page hides `"notes"` from what it
  renders even when it's present in `enabled` — that filter happens at render time in
  `buildDateView()` and does **not** modify this stored value. My Space (a different screen, see
  `wp-myspace-layout-v1`) is unaffected and still shows it if it has it in its own layout.
- **Removed built-in widget:** `"vibes"` ("Today's Vibe") used to be a selectable built-in widget
  id here. The feature was removed entirely (widget, picker UI, `VIBES`/`customVibes` data model,
  `wp-vibes-custom-v1`). `sanitizeWidgetConfig()`'s existing orphaned-id cleanup (originally
  written for a deleted *custom* widget) also self-heals this: any account with `"vibes"` still
  sitting in a saved `enabled` array has it silently dropped on next load, the same way a deleted
  custom widget's id already was.
- **Write:** whenever a widget is added/removed/reordered, or a custom widget created/edited/
  deleted, via the "Customize widgets" screen.

### `wp-widget-daily-v1`
- **Purpose:** the per-day *values* for whatever widgets `wp-widget-config-v1` lists — kept in a
  separate key on purpose so enabling a widget for future days never touches past days' data.
- **Shape:** object keyed by `dateKey`, each value an object keyed by `widgetId`. The value's type
  depends on that widget's `kind` (from `wp-widget-config-v1.customWidgets` for custom ones, or
  the built-in `SYSTEM_WIDGETS` table for system ones):

  | `kind`        | stored value type                          |
  |----------------|---------------------------------------------|
  | `text`         | string |
  | `number`       | number, or `null` if cleared |
  | `counter`      | number ≥ 0 |
  | `rating`       | number, 0–5 |
  | `checklist`    | `{ id: number, title: string, done: boolean }[]` |
  | `toggle`       | boolean |
  | `scale`        | number, 1–5 |
  | `timer`        | boolean — "marked done today"; the displayed streak (`widgetStreakLabel`) is never stored, always recomputed fresh from consecutive `true` days via `widgetStreakCount()` |
  | `healthSteps`  | number — the built-in `steps` widget (changed from `kind:'number'` this pass). This is a **cache of the last real Health read**, written by `STEPS_SOURCE.fetchStepsFor()` once permission is granted — never a manually-typed value. See `docs/IOS_READINESS.md`'s Steps/HealthKit section. |
  | `journalMoment`| **nothing** — the 7 Journal-bridge widgets (`momentPhoto`, ...) never write here at all; see the `wp-widget-config-v1` entry above. |

- **Write:** the whole object re-saved on every widget-value change (except `journalMoment`-kind
  widgets, which never touch this key).
- **Merge-on-first-sign-in:** yes, per-date-key union.

### `wp-myspace-layout-v1`
- **Purpose:** the My Space dashboard's own draggable/resizable grid — independent from
  `wp-widget-config-v1` even though several ids overlap (e.g. both can reference `"mood"`).
- **Shape:**
  ```
  {
    widgets: {
      id: string,      // a "launcher" card ("myday","calendar","goals","expenses","mymedia"),
                        // a system widget id (same namespace as wp-widget-config-v1), or a
                        // custom widget id
      x: number, y: number,   // grid position
      w: number, h: number,   // grid size
      order: number,
      color: "cream" | "yellow" | "blue" | "green" | "pink" | "purple" | "red"
    }[]
  }
  ```
- **Default:** `null` until first computed (seeded from the widgets picked during onboarding, or
  a fixed starter set `['myday','calendar','mood','water','sleep','tasks','goals','expenses','mymedia']`
  if none were picked).
- **Write:** on every add/remove/drag/resize/reorder/recolor on the My Space screen.
- **Merge-on-first-sign-in:** no special handling — whichever full object exists (cloud if
  present, otherwise local) is used as-is.

### `wp-expenses-v1`
- **Purpose:** the single transaction ledger behind Budget, Month, and Day expense sections —
  and the only place income can exist.
- **Shape:** array of:

  | field       | type              | notes |
  |-------------|-------------------|-------|
  | `id`        | string            | `crypto.randomUUID()` or fallback |
  | `date`      | string            | `"YYYY-MM-DD"` |
  | `amount`    | number            | |
  | `currency`  | string            | currency code, always the ORIGINAL currency the transaction was entered in — never rewritten when "View in" changes elsewhere in Budget. `ensureExpenseCurrencies()` (called once per Budget render) backfills `defaultCurrency` onto any record missing this field, so nothing crashes or gets dropped; it never touches a record that already has one |
  | `category`  | string            | free text / select value, may be `""` |
  | `note`      | string            | may be `""` |
  | `createdAt` | number            | `Date.now()` |
  | `updatedAt` | number            | `Date.now()`, updated on edits |
  | `type`      | `"income"` \| *(absent)* | **absent means expense.** This is the one place a missing field carries real meaning — every record created before Budget existed, and every one still created from Month/Day's own "add expense" forms, has no `type` field at all and must be treated as an expense. Only Budget's own "Income" toggle writes `type:"income"`. |

- **Read by three different filtered views over this same array:**
  - `expensesForMonth(monthKey)` / `expensesForDate(dateKey)` — **expense-only**
    (`type !== 'income'`), used by Month, Day, and the My Space "Monthly Expenses" card.
  - `transactionsForMonth(monthKey)` — **both types**, used only by Budget.
- **Wallet balance is never stored** — it's always computed as
  `initialBalance (wp-initial-balance-v1) + sum of every record in this array`. Don't look for a
  stored balance key; there isn't one.
- **Write:** whole array re-saved on add/edit/delete.
- **Merge-on-first-sign-in:** yes, but by **id union** (`mergeRecordArrayById` — append any local
  record whose `id` isn't already in the cloud array), not the date-keyed-object merge used for
  the keys above.
- **One-time client-side migration (already shipped, not relevant going forward):** the very
  first time this key doesn't exist yet, the code scans `localStorage` for old
  `wp-month-expenses-v1-<monthKey>` keys and folds them in. Nothing for iOS to redo.

### `wp-expense-currencies-v1` ("Active Currencies")
- **Purpose:** which currencies the user has actually opted into tracking — the only ones
  offered when picking a transaction's currency, and what "Spending by Currency" lists on
  Budget. Managed from **Settings → Currencies** (`openCurrencySheet()`), which is now the one
  dedicated place for this — Month/Day/Budget's own inline "+ currency" quick-adds still exist
  for convenience but write to this exact same array, not a parallel one.
- **Shape:** `string[]` of currency codes.
- **Default:** `["EUR","RSD"]`.
- **Selectable domain:** picked from `WORLD_CURRENCIES`, a static list of ~150 real ISO 4217
  currency codes (searchable by code or name in the Currencies sheet) — no longer the old
  hardcoded 5 (`ALLOWED_CURRENCIES` is now *derived from* `WORLD_CURRENCIES.map(w=>w.c)`, kept
  under that name purely so every existing call site that filtered against it
  (`currencyOptionsHtml`/`fillCurrencySelect`/`renderCurrencyChipsInto`/`addCurrencyFlow`/
  `editCurrencyOptionsHtml`) needed zero changes). An older/edited record can in principle still
  hold a code outside even this larger list — nothing enforces it retroactively.
- **Invariant:** the UI never lets this shrink to zero — removing the last remaining currency
  chip is a no-op (button disabled).
- **Write:** on add/remove, from the Currencies sheet or any inline "+ currency" quick-add.

### `wp-expense-display-ccy-v1` ("View in")
- **Purpose:** the ONE currency Budget's aggregates (My Balance, Income/Spent/Net, the spending
  ring, and the Monthly Budget progress bar's *comparison*) are converted into for display —
  and also what the Month view's own "Total in ___" row still uses, unchanged. This is the
  fix for the old screen showing "Spent EUR / Income EUR / Spent RSD / Income RSD" all at once:
  now there is exactly one converted total on screen at a time, chosen here, plus a separate
  compact **original-currency** breakdown (see `wp-expenses-v1` below) that never converts
  anything.
- **Shape:** single currency-code string.
- **Default:** the first entry of `wp-expense-currencies-v1` (or `"EUR"` if that's empty).
- **Write:** the "View in" select on Budget's wallet-balance card (`walletViewInSelect`), or
  Month's "Total in ___" select — both write this same key.

### `wp-default-currency-v1` ("Primary Currency")
- **Purpose:** the currency Initial Balance is denominated in, the currency a brand-new Monthly
  Budget target defaults to, and the preferred pick in currency dropdowns. Set from
  **Settings → Currencies** (`currencyPrimarySelect`).
- **Shape:** single currency-code string.
- **Default:** `"EUR"`.
- **Invariant:** changing it always ensures the new value is also present in
  `wp-expense-currencies-v1` (pushed in if missing) — a Primary Currency you can't otherwise
  transact in would be a broken state. Conversely, the currency currently set here can never be
  removed from Active Currencies while it's still Primary — its delete chip is disabled and the
  removal handler re-checks `removed===defaultCurrency` at runtime (not just the disabled
  attribute), so it can't be bypassed by re-enabling the button in devtools. Switch Primary to a
  different active currency first, then the old one becomes removable.

### `wp-initial-balance-v1`
- **Purpose:** the wallet's one-time starting balance, denominated in Primary Currency
  (`wp-default-currency-v1`).
- **Shape:** number.
- **Default:** `0`.
- **UI:** moved out of Budget's main screen (it used to sit there permanently as
  "Initial balance: €0.00 · Edit", which read as confusing clutter) into
  **Settings → Currencies**, as an optional field. The stored value and the balance formula
  (`initialBalance + income - expenses`, computed fresh every render, never stored) are
  unchanged — existing balances keep working exactly as before, just edited from a different
  screen (`initialBalanceRowHtml()`/`bindInitialBalanceEditor()`, same element ids as before,
  just rendered inside the Currencies sheet instead of the wallet-balance card).

### `wp-monthly-budget-target-v1`
- **Purpose:** optional recurring monthly spending goal shown in Budget, in its OWN currency —
  a target set as €2,000 stays €2,000 even while Budget is being viewed in RSD; only a small
  "≈ converted" line changes, never the stored goal itself.
- **Shape:** `{ amount: number, currency: string }`.
- **Default:** `{ amount:0, currency:"EUR" }` (`amount:0` means "no target set", same meaning
  the old bare `0` had).
- **Migration:** this key used to be a bare `number`, implicitly in whatever `defaultCurrency`
  was at the time (the app had no other currency concept for it then). `ensureMonthlyBudgetTargetShape()`
  — called at the top of every Budget render — converts an old numeric value into
  `{ amount: <that number>, currency: defaultCurrency }` the first time it's encountered,
  preserving the exact goal a user already had; nothing is lost.
- **Comparison currency:** the progress bar/spent-vs-remaining text always compares spending
  converted into the target's OWN currency
  (`convertMapToWalletCcy(spentByCcy, monthlyBudgetTarget.currency)`), never into "View in" —
  so the goal means the same thing regardless of what the rest of the page is currently showing.

### `wp-fx-rates-v1-<BASE>` (one row per base currency actually used, e.g. `wp-fx-rates-v1-EUR`)
- **Purpose:** a **cache**, not user data — currency conversion rates for Budget.
- **Shape:** `{ base: string, rates: { [currencyCode]: number }, fetchedAt: number }`.
- **Refresh:** refetched from external FX APIs whenever older than 12 hours
  (`FX_MAX_AGE_MS = 12*60*60*1000`); served stale-with-a-label if every provider is unreachable.
- **iOS note:** safe to ignore/drop entirely — it will simply refetch on first use. Don't spend
  migration effort on it.

### `wp-timezone-v1`
- **Purpose:** the timezone used for date/time display.
- **Shape:** IANA timezone string, e.g. `"Europe/Belgrade"`.
- **Default:** auto-detected via `Intl.DateTimeFormat().resolvedOptions().timeZone`, falling back
  to `"UTC"` if detection throws.

### `wp-notif-prefs-v1`
- **Purpose:** notification preference toggles in Settings.
- **Shape:** `{ dailyReminder: boolean, taskReminders: boolean, eveningReminder: boolean }`, all
  default `false`.
- **Important:** this is a **preference with no behavior behind it yet**. There is no scheduling,
  no permission request, no actual notification code anywhere in the app — toggling these
  switches only writes this object. The Settings copy says so explicitly ("not active yet — this
  just saves your preference for when reminders launch"). Don't build iOS notification logic
  that assumes these flags currently mean anything operational.

### Stickers — removed

The decorative sticker feature (`wp-customstickers-v5`, `wp-stickerzones-v5`, built-in packs
under `/assets/stickers/`, the sticker FAB/sheet UI) was removed entirely as part of the
Journal-centric product redesign. It never overlapped with any other feature's data — no
migration is needed for accounts that had placed stickers; that data simply stops being read.
The unrelated per-task mood emoji (`todo.vibe`, see the `wp-days-v5` table above) is a
different feature and was not touched.

### `wp-month-goals-v1-<monthKey>` (one row per month, `monthKey = "YYYY-MM"`)
- **Purpose:** the Month view's goals checklist for that specific month.
- **Shape:** array of `{ id: number, title: string, done: boolean }`.

### `wp-month-favorites-v1-<monthKey>`
- **Purpose:** the Month view's "favorites" categories for that specific month.
- **Shape:** array of `{ id: number, label: string, entries: { id: number, text: string }[] }`.

### `wp-month-notes-v1-<monthKey>`
- **Purpose:** free-text notes for that specific month.
- **Shape:** plain string.

---

## Keys that are intentionally *not* in this contract (local-only, never synced)

These bypass `save()`/`load()` entirely and talk to `localStorage` directly — they describe
*this browser/device*, not the user's account, so they have no place in `app_data` and should
**not** be treated as something an iOS client needs to read or write compatibly:

| key | purpose |
|-----|---------|
| `wp-offline-mode-v1` | `"1"` if this device is in "Continue offline" mode (no Supabase session at all) |
| `wp-cloud-migrated-v1` | `"1"` once this device has done its one-time first-sign-in merge (see above) |
| `wp-cloud-last-user-id-v1` | the last user id signed in on this device, used to detect an account switch and wipe stale local data before a different account's data can be polluted by leftovers |

## Currency codes, category values, and other "free text" fields

Several fields above (`currency`, `category`, custom widget `type`) are plain
strings rather than a fixed enum enforced by storage — the *current* valid values are whatever
the Web UI's own dropdowns offer today. If those dropdowns' option lists change in the Web app
in the future, this document's "current values" call-outs (not the general shape) would need a
quick re-check against the code rather than being assumed to still be exhaustive.
