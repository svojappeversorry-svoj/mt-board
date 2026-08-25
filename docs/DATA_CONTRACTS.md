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

### `wp-avatar-v1`
- **Purpose:** chosen avatar character.
- **Shape:** string id from the 10-item `AVATAR_COLLECTION` (e.g. `"angel-pig"`, `"glam-cow"`,
  `"beach-bird"`, `"koala"`, `"chaotic-monkey"`, `"hamster-glasses"`, `"duck"`,
  `"capybara-rose"`, `"fairy-horse"`, `"glam-dog"`), or `""` if never chosen.
- **Default:** `""`.
- **Write:** Settings avatar grid; once during onboarding.

### `wp-onboarding-complete-v1`
- **Purpose:** whether the onboarding flow has run.
- **Shape:** boolean.
- **Default:** `false`.
- **Write:** set to `true` exactly once, at the end of onboarding.

### `wp-days-v5`
- **Purpose:** the core per-day record — mood, water, sleep, tasks, notes, vibes for that date.
  This is the single largest and most-written key in the app.
- **Shape:** an object keyed by `dateKey` (`"YYYY-MM-DD"`, local calendar date). Each value:

  | field      | type                                             | default   | notes |
  |------------|--------------------------------------------------|-----------|-------|
  | `mood`     | number, 0–4                                       | `2`       | slider value |
  | `water`    | number                                            | —         | **legacy** "glasses" count (0–8ish); no longer written by current code, kept only so old rows can be one-time-migrated into `waterMl` on first read |
  | `waterMl`  | number                                             | `0`       | current water tracker unit, millilitres |
  | `waterLog` | `number[]`                                        | `[]`      | each entry is one ml amount added, in order — powers "undo last" |
  | `sleep`    | number, 0–12, step 0.05                           | `7`       | hours |
  | `todos`    | `{ text: string, done: boolean, vibe: string }[]` | `[]`      | **no `id` field** — a todo is addressed only by its array index within that day; moving/toggling/deleting all operate on `todos[i]` |
  | `notes`    | string                                            | `""`      | free-text "what happened today" |
  | `vibes`    | `string[]`                                        | `[]`      | ids into the built-in `VIBES` list or into `wp-vibes-custom-v1` |

- **Defaulting/migration on read:** `ensureDayData(key)` lazily creates a day record with the
  defaults above the first time it's touched, and backfills `vibes`/`waterLog`/`waterMl` onto
  *existing* day objects that predate those fields. **An iOS reader must apply the same
  defaulting** — older stored days are not guaranteed to already have every field present.
- **Read:** the entire object loaded once into memory at app start (`let daysData = load(...)`).
- **Write:** the entire `daysData` object is re-saved on *every* mutation — adding/checking off/
  deleting/moving a task, logging or undoing water, changing mood or sleep, editing notes, or
  adding/removing a vibe.
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

### `wp-journal-v1`
- **Purpose:** the Journal tab's timeline — freeform personal entries, each its own
  self-contained record (a day can have zero, one, or several). Added for the 4-tab
  restructuring (Today / Budget / Journal / You); not present in earlier versions of the app.
- **Shape:** a flat array of:

  | field       | type       | notes |
  |-------------|------------|-------|
  | `id`        | string     | `crypto.randomUUID()`, or a timestamp+random fallback string |
  | `date`      | string     | `dateKey` (`YYYY-MM-DD`) the entry is *about* — independent of `createdAt` |
  | `text`      | string     | freeform entry text, default `""` |
  | `mood`      | number \| `null` | 0–4, same scale/faces as `wp-days-v5.mood` (`moodFace()`) |
  | `vibes`     | `string[]` | up to 4 ids from the same `VIBES` table (and any `wp-vibes-custom-v1` custom vibes) used on My Day — **not** a separate tag vocabulary |
  | `photos`    | array      | own attachments, **not** shared with `wp-photos-v1`: `{ id: string, src: string (data: URL, same resizeImageJPEG pipeline as Day photos) }[]`, capped at `MAX_PHOTOS_PER_DAY` (20) per entry |
  | `expenseId` | string     | optional — id of a row in `wp-expenses-v1` for the same `date`, or `""` for no link |
  | `createdAt` | number     | `Date.now()` at save time; also the tiebreaker for ordering multiple entries on the same `date` |
  | `updatedAt` | number     | set equal to `createdAt` at save time (entries are delete-only today, never edited in place, so this never actually diverges from `createdAt` yet) |

- **Default:** `[]`.
- **Deliberately NOT shared storage:** an entry's photos are its own array, not
  `wp-photos-v1[date]` — a day can have several journal entries, so there's no single "the
  day's photos" slot to write into. `expenseId` is a reference by id into `wp-expenses-v1`,
  not a copy of that transaction's fields, so editing/deleting the linked transaction in
  Budget is not reflected back onto the journal entry (a dangling `expenseId` is simply
  treated as "no linked transaction" — `journalEntryHtml()` looks it up by id at render time
  and shows nothing if it's gone).
- **Write:** the whole array is re-saved on every entry add or delete.
- **Merge-on-first-sign-in:** **no** — not one of the four keys with special merge behavior
  (see above). A first sign-in on a browser with local-only journal entries and an account
  that already has cloud journal entries will have the cloud copy win, same as every other
  key not in that special list. If Journal turns out to need the same offline-safety
  guarantee as Days/Photos/Widget-daily/Expenses, add it to that merge list explicitly rather
  than assuming it already behaves that way.

### `wp-widget-config-v1`
- **Purpose:** which optional widgets appear on the **My Day** detail page, in what order, plus
  any user-defined custom widgets. (Separate from My Space's own layout — key below.)
- **Shape:**
  ```
  {
    enabled: string[],       // ordered widget ids, e.g. ['mood','water','sleep','vibes','tasks','notes']
                              // ids are either built-in ("mood","water","sleep","steps","vibes",
                              // "tasks","notes","gratitude","dailyHighlight","freeText","photos",
                              // "music","movie","favoriteThing") or a custom widget's own id
                              // (format "custom:<timestamp><random>")
    customWidgets: {
      id: string,             // "custom:<timestamp><random>"
      name: string,
      description: string,
      type: "text" | "checklist" | "number" | "counter" | "rating"
    }[]
  }
  ```
- **Default:** `{ enabled:['mood','water','sleep','vibes','tasks','notes'], customWidgets:[] }`.
- **Limits enforced client-side (not in the stored data):** at most 10 built-in widgets enabled
  at once, at most 3 custom widgets total.
- **Known display-only exception:** the dedicated My Day page hides `"vibes"` and `"notes"` from
  what it renders even when they're present in `enabled` — that filter happens at render time in
  `buildDateView()` and does **not** modify this stored value. My Space (a different screen, see
  `wp-myspace-layout-v1`) is unaffected and still shows them if it has them in its own layout.
- **Write:** whenever a widget is added/removed/reordered, or a custom widget created/edited/
  deleted, via the "Customize widgets" screen.

### `wp-widget-daily-v1`
- **Purpose:** the per-day *values* for whatever widgets `wp-widget-config-v1` lists — kept in a
  separate key on purpose so enabling a widget for future days never touches past days' data.
- **Shape:** object keyed by `dateKey`, each value an object keyed by `widgetId`. The value's type
  depends on that widget's `kind` (from `wp-widget-config-v1.customWidgets` for custom ones, or
  the built-in `SYSTEM_WIDGETS` table for system ones):

  | `kind`      | stored value type                          |
  |-------------|---------------------------------------------|
  | `text`      | string |
  | `number`    | number, or `null` if cleared |
  | `counter`   | number ≥ 0 |
  | `rating`    | number, 0–5 |
  | `checklist` | `{ id: number, title: string, done: boolean }[]` |
  | *(the built-in `steps` widget explicitly declares `kind:'number'`)* | number |

- **Write:** the whole object re-saved on every widget-value change.
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
  | `currency`  | string            | currency code |
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

### `wp-expense-currencies-v1`
- **Purpose:** which currencies are currently tracked in Budget.
- **Shape:** `string[]` of currency codes.
- **Default:** `["EUR","RSD"]`.
- **Current selectable domain:** the "+ Currency" picker only offers
  `["EUR","RUB","USD","RSD","GEL"]` (`ALLOWED_CURRENCIES`) — this is a UI constraint, not
  something storage enforces, so don't assume every stored currency code is necessarily one of
  these five (older/edited records could in principle hold anything).
- **Write:** on "+ Currency".

### `wp-expense-display-ccy-v1`
- **Purpose:** which currency Budget's month total is converted into for display.
- **Shape:** single currency-code string.
- **Default:** the first entry of `wp-expense-currencies-v1` (or `"EUR"` if that's empty).

### `wp-default-currency-v1`
- **Purpose:** currency pre-filled on new-expense forms.
- **Shape:** single currency-code string.
- **Default:** `"EUR"`.

### `wp-initial-balance-v1`
- **Purpose:** the wallet's one-time starting balance.
- **Shape:** number.
- **Default:** `0`.

### `wp-monthly-budget-target-v1`
- **Purpose:** optional monthly spending cap shown in Budget.
- **Shape:** number.
- **Default:** `0` (treated as "no target set").

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

### `wp-vibes-custom-v1`
- **Purpose:** user-created "vibe" tags, in addition to the ~14 built-in ones (the built-ins live
  in a hardcoded `VIBES` constant and are never stored/synced).
- **Shape:** array of:
  `{ id: string ("customvibe:<timestamp><random>"), emoji: string (≤4 chars), label: string (≤40 chars), c1: string (hex color), c2: string (hex color), fg: string (hex color) }`.
  `c1`/`c2`/`fg` come from a small fixed palette rotation, not free color choice.
- **Limit:** at most 10 (`MAX_CUSTOM_VIBES`).

### `wp-customstickers-v5`
- **Purpose:** user-uploaded decorative stickers (separate from the 4 built-in sticker packs,
  which are static files under `/assets/stickers/` and never stored here).
- **Shape:** array of `{ id: number (Date.now()+Math.random() — a number, not a string, unlike
  every other id in this document), src: string (base64 PNG data URL) }`.
- **Limit:** at most 60 (`MAX_STICKERS`).

### `wp-stickerzones-v5`
- **Purpose:** where decorative stickers have been placed. Placement only exists on the Date
  View (My Day detail page) today — there is no other placement surface.
- **Shape:** object keyed by `dateKey`, each value an array of:
  ```
  {
    iid: number,           // Date.now()+Math.random() — this placed instance's own id
    sid: string | number,  // which sticker: "b:<packId>:<fileBaseName>" for a built-in pack
                            // (packId one of "digital-chrome","y2k-vixen","dark-romance",
                            // "petal-botanical" — see the iOS audit's note on these ids not
                            // matching current theme names), or a wp-customstickers-v5 entry's
                            // numeric id for a custom upload
    x: number, y: number,  // percentage position within the page
    rot: number,           // degrees
    scale: number
  }
  ```
- **Limit:** at most 14 placed stickers per day.

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

Several fields above (`currency`, `category`, custom widget `type`, sticker pack ids) are plain
strings rather than a fixed enum enforced by storage — the *current* valid values are whatever
the Web UI's own dropdowns offer today. If those dropdowns' option lists change in the Web app
in the future, this document's "current values" call-outs (not the general shape) would need a
quick re-check against the code rather than being assumed to still be exhaustive.
