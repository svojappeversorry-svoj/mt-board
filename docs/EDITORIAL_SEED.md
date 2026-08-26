# Editorial seed content — the official @svoj account

Populates a fresh install's Explore feed with ~130 curated "SVOJ editorial picks" so it never
looks empty before the app has real users. This is **not** simulated user activity — there is
exactly one account (`@svoj`), it is clearly an official account under the hood (not a disguised
admin/bot), and no fake engagement (likes, follows, comments) exists anywhere in this app to
begin with.

## Why this needs manual steps, same as the other two tables

This session cannot reach your real Supabase project (no dashboard access, no service-role key,
and this sandbox's network policy blocks the Supabase JS SDK's CDN entirely — see
`docs/SUPABASE_ENVIRONMENTS.md`). Every step below was instead **verified end-to-end against a
real local Postgres instance** standing in for Supabase's schema (see "How this was verified"
below) — the SQL itself is proven correct and idempotent, just not yet run against your actual
project.

## What you need to do (three steps, ~5 minutes)

### 1. Create the @svoj account

Supabase Dashboard → **Authentication → Users → Add user**. Use email
**`svojappeversorry@gmail.com`** (this is the email `docs/sql/editorial_seed.sql` is generated to
look up — see `SVOJ_EMAIL` in `scripts/generate_editorial_seed_sql.py` if you ever need to change
it), any password, and check **Auto Confirm User** so no email verification is required.

### 2. Create the two tables the seed depends on (skip any you already have)

Run each block below in **SQL Editor → New query** if the table doesn't already exist in your
project. This is the exact mistake that produces `ERROR: 42P01: relation "public.usernames" does
not exist` when running step 3 — the seed inserts a row into `usernames`, so that table must
exist first.

**`public.usernames`** (full policy set in `docs/USERNAMES_TABLE.md`):

```sql
create table if not exists public.usernames (
  username    text primary key,
  user_id     uuid not null unique references auth.users(id) on delete cascade,
  created_at  timestamptz not null default now()
);
alter table public.usernames enable row level security;
create policy "anyone can view usernames" on public.usernames for select using (true);
create policy "individuals can claim their own username" on public.usernames for insert with check (auth.uid() = user_id);
create policy "individuals can update their own username" on public.usernames for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "individuals can delete their own username" on public.usernames for delete using (auth.uid() = user_id);
```

**`public.public_journal_moments`** (full policy set + shareable-URL notes in
`docs/JOURNAL_PUBLIC_TABLE.md`) — if this table already exists from an earlier step, just run the
one `alter table` line to add `is_editorial`:

```sql
create table if not exists public.public_journal_moments (
  id            text primary key,
  user_id       uuid not null references auth.users(id) on delete cascade,
  author        text not null default '',
  type          text not null,
  title         text not null default '',
  description   text not null default '',
  image         text,
  thumb         text,
  external_url  text,
  location      jsonb,
  artist        text,
  is_editorial  boolean not null default false,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  published_at  timestamptz not null default now()
);
alter table public.public_journal_moments add column if not exists is_editorial boolean not null default false;
alter table public.public_journal_moments enable row level security;
create policy "anyone can view public journal moments" on public.public_journal_moments for select using (true);
create policy "individuals can insert their own public journal moments" on public.public_journal_moments for insert with check (auth.uid() = user_id);
create policy "individuals can update their own public journal moments" on public.public_journal_moments for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "individuals can delete their own public journal moments" on public.public_journal_moments for delete using (auth.uid() = user_id);
create index if not exists public_journal_moments_published_at_idx on public.public_journal_moments (published_at desc);
```

### 3. Run the seed migration

Supabase Dashboard → **SQL Editor → New query** → paste the entire contents of
`docs/sql/editorial_seed.sql` (it now looks up the account by `svojappeversorry@gmail.com`) →
**Run**.

That's it. This claims the `svoj` username for the account from step 1 and inserts all 134
editorial moments, each already public, each attributed to `@svoj`. Re-run end-to-end against a
real local Postgres 16 instance after this change (fresh schema, real generated SQL, real email)
to confirm it still lands 134 rows and 1 username row, and that running it twice in a row leaves
both counts unchanged.

## Safe to run again

The whole migration is one `do $$ ... $$` block that upserts every row by its stable id
(`svoj-seed-0001` … `svoj-seed-0134`) via `on conflict (id) do update`, and the username claim
via `on conflict (user_id) do update`. Running it a second time (e.g. after fixing a typo, or
re-running the generator with edited content) **never creates duplicates** — it just updates the
existing rows in place. Verified by actually running the generated SQL twice in a row against a
real Postgres database and confirming the row count stayed at 134 both times (see below).

## Removing, replacing, or excluding editorial content later

Every seed row (and only seed rows) has `is_editorial = true`. That's the one thing you need:

```sql
-- Remove all editorial content
delete from public.public_journal_moments where is_editorial = true;

-- Or just stop counting it in some future analytics query
select ... from public.public_journal_moments where is_editorial = false;
```

No other account, table, or code path is affected either way — private user Journal data
(`app_data`/`wp-journal-moments-v1`) has no concept of `is_editorial` and was never touched by
any of this.

## Regenerating the content

The actual dataset lives in `scripts/generate_editorial_seed_sql.py`, not in the `.sql` file
directly — edit the Python lists there (grouped by type: `RECIPE`, `PLACE`, `SONG`, `MOVIE`,
`LINK`, `NOTE`) and re-run:

```sh
python3 scripts/generate_editorial_seed_sql.py
```

This overwrites `docs/sql/editorial_seed.sql` and validates the dataset first (every row has a
real title/description length, every URL matches a real `https://` pattern, no duplicate ids) —
it refuses to write a broken file. Commit both the script and the regenerated `.sql` file.

## Content design decisions

- **No `photo`-type moments.** Sourcing ~20+ distinct, appropriately-licensed photographs for
  unrelated food/travel/fashion/interior subjects isn't achievable here without either
  downloading copyrighted images (explicitly out of scope) or reusing this app's own avatar
  artwork (thematically wrong — cartoon animal characters don't belong on a recipe entry). The
  original request's own instructions allow this: *"If a valid external URL/image cannot be used
  for a particular type, choose another suitable piece of content instead."* Every entry instead
  uses one of the other 6 types (recipe/place/song/movie/link/note), all of which already render
  a clean type-icon fallback with no thumbnail — an existing, first-class UI state in Explore,
  not a degraded one.
- **Every URL is real and guaranteed to resolve.** Each one is either a *search* URL on a real,
  major, stable site (the domain and route are real regardless of the specific query — e.g.
  `allrecipes.com/search?q=...`, `open.spotify.com/search/...`, `imdb.com/find/?q=...`,
  `google.com/maps/search/...`), a real homepage of a well-known site, or a specific Wikipedia
  article for a well-known, unambiguous topic. None are fabricated deep links (no invented blog
  slug, no guessed video/track/listing id) — matching the requirement not to invent URLs that
  lead nowhere.
- **Balanced across 6 types**, ~22–23 each: recipe, place, song, movie, link, note — covering the
  sub-themes from the original brief (easy chicken/pasta/desserts/breakfast/healthy/dinner for
  recipes; cafés/restaurants/views/travel/local for places; summer/late-night/romantic/getting-
  ready/chill for songs; fashion/comfort/romantic/thriller/rewatch for movies; fashion & visual
  inspiration folded into link+note since Journal has no separate "fashion" type).
- **Interleaved, not clustered.** The generator round-robins across all 6 categories and assigns
  strictly descending `published_at` timestamps in that exact order, so Explore's default
  "newest first" sort naturally mixes types — recipe, place, song, movie, link, note, recipe,
  place, ... — rather than showing 23 recipes in a row.
- **Written for search, not just for looks.** Titles and descriptions use specific, natural
  language ("Creamy Garlic Chicken for a Weeknight Win", not "Nice recipe") so both the existing
  plain-text Explore search and the documented future hybrid semantic search
  (`docs/SEARCH_ARCHITECTURE.md`) have real signal to match against — a search for "chicken
  recipes" or "romantic movies" should surface these entries.

## How this was verified (this session)

This sandbox cannot connect to your real Supabase project, so verification instead ran the
*actual* generated SQL end-to-end against a real local PostgreSQL 16 instance with a minimal
stand-in `auth.users` table and the exact same `usernames`/`public_journal_moments` schema from
`docs/USERNAMES_TABLE.md`/`docs/JOURNAL_PUBLIC_TABLE.md` (including the `is_editorial` column):

- ✅ The full migration ran with zero SQL errors.
- ✅ Exactly 134 rows landed in `public_journal_moments`, all with `is_editorial = true`.
- ✅ Per-type counts: recipe 23, place 23, note 22, movie 22, song 22, link 22 — balanced, no
  type dominating.
- ✅ The `usernames` row (`svoj` → the test account's id) was created correctly.
- ✅ `place`-type rows populated `location.url`/`location.name` correctly (not `external_url` —
  matching exactly what `journalOpenExploreDetail()`'s "Open Map" link reads for that type).
- ✅ Re-running the entire migration a second time left both row counts unchanged (134 and 1) —
  idempotency confirmed empirically, not just by reading the `on conflict` clauses.
- ✅ The generator's own `validate()` step passed: no duplicate ids, no missing/short title or
  description, every URL matches a real `https://` pattern.

What this *doesn't* verify (needs the real project, once you complete the 3 steps above):
- That Explore actually renders these 134 rows correctly in the live app against your real
  Supabase project (client code was verified by direct code reading instead — see below — since
  the rendering logic is generic and already exercised by every other public moment in Explore).
- That RLS in your real project behaves as expected for anonymous/authenticated reads (already
  covered by the existing, unmodified policies from `docs/JOURNAL_PUBLIC_TABLE.md` — nothing
  about this feature changes those policies).

## Client-side behavior — verified by reading the actual code, no changes needed

- **No technical label anywhere.** `journalExploreCardHtml()`/`journalOpenExploreDetail()` in
  `index.html` only ever destructure the specific fields they use (`title`, `description`,
  `type`, `author`, `thumb`, `image`, `external_url`, `location`, `artist`) — `is_editorial`
  sitting unused in the row object is automatically invisible. `@svoj`'s moments display exactly
  like any other user's; there is no "Admin"/"System"/"Seed"/"Bot" label defined anywhere in this
  app to begin with.
- **Author displays as `@svoj`.** Same `author` field, same rendering path as every other public
  moment (`t('journalByAuthor', {name: row.author})` → "by @svoj").
- **Save to My Journal already does exactly what was asked.** `journalSaveExploreItemToMyJournal()`
  builds the saved copy from a fixed list of named fields (never a wildcard copy of the row) and
  unconditionally sets `visibility: 'private'` — an editorial moment saved by a real user becomes
  a fully independent, private copy in their own Journal, with `savedFrom: { momentId, author }`
  provenance (so their own moment can show "originally by @svoj"), exactly like saving from any
  other user's public moment. The user can later make their own saved copy public again through
  the normal Make Public flow (which still requires a link + description, already satisfied since
  it's copied from the original).
- **No duplicate media created.** The saved copy reuses the already-compressed `image`/`thumb`
  strings by value (there are none for these entries, since no `photo`-type moments exist in the
  seed set) — same "no re-compression" behavior as saving from a real user's public photo moment.
- **Private data isolation is unaffected.** Editorial content only ever exists in
  `public_journal_moments` — a real user's private Journal (`app_data`) has no code path that
  reads from or writes to it except through the existing, unmodified Save-to-My-Journal flow.

## Verification checklist (mapped to the original 11 points)

1. **@svoj exists correctly** → verify in Supabase Dashboard after step 1+3: Authentication shows
   the account, Table Editor → `usernames` shows one row (`svoj` → that account's id).
2. **~100–150 editorial moments available** → `select count(*) from public_journal_moments where is_editorial;` should return 134.
3. **All are public** → true by construction; `public_journal_moments` only ever holds public
   moments (see `docs/JOURNAL_PUBLIC_TABLE.md`) — there is no visibility column to check.
4. **Appear in Explore** → open Explore in the app after running the migration; the grid should
   show a mix of types immediately, even signed in as a brand-new account.
5. **Users can open them** → tap any card; the detail sheet should show title/description/link
   exactly like any other public moment.
6. **Save to My Journal works** → tap it from an @svoj moment's detail view.
7. **Saved moments become private** → open the saved copy in your own Journal; it should show the
   "Private" badge, and `savedFrom` should read "originally by @svoj".
8. **Images load correctly and are optimized** → N/A by design for this seed set (no `photo`-type
   entries, see "Content design decisions" above) — every entry renders the existing type-icon
   fallback, which requires no image data at all.
9. **Search finds editorial content** → try "chicken", "café", "song", "movie" etc. in Explore's
   search box — the plain-text search already matches title/description/type, and these entries
   were written with exactly that in mind.
10. **Doesn't appear as fake user activity in analytics** → there is no analytics/admin surface
    anywhere in this app today, so there's nothing to pollute; the `is_editorial` flag exists
    specifically so a future one can exclude it trivially.
11. **Private user Journal data stays isolated** → unaffected; see "Private data isolation" above.

Items 1–2, 4–7, 9 require actually completing the 3 setup steps against your real Supabase
project — this session verified the SQL itself is correct and idempotent (see above) and that
the client code path is generic and already exercised by the existing Journal/Explore feature,
but cannot exercise the live network round-trip from here.
