# Journal Explore — the `public_journal_moments` table

This is a **required manual step**, not an optional one: until this table exists in the PROD
Supabase project, "Make Public", Explore, and "Save to My Journal" are inert no-ops (the code
calls Supabase, gets an error because the table doesn't exist, logs a console warning, and
otherwise does nothing) — every *private* Journal feature works today regardless of this step.

## Why a new table, and why this session can't create it

Every other piece of user data in this app (`wp-days-v5`, `wp-photos-v1`, `wp-expenses-v1`,
now `wp-journal-moments-v1`, ...) lives in the single `app_data` table, whose row-level security
is deliberately "the owner can read/write their own row only" (`auth.uid() = user_id`, see
`docs/SUPABASE_ENVIRONMENTS.md`). That is exactly correct for private data, and it means **no
row in `app_data` can ever be readable by a second signed-in user** — the whole point of RLS
there. A genuinely public Explore feed needs a table with the opposite read rule (anyone can
`select`, but only the owner can `insert`/`update`/`delete` their own rows), which is a schema
change against your real Supabase project. This session only holds the client-side anon key —
running SQL against your project requires your Supabase dashboard, the same limitation already
documented for creating the DEV project in `docs/SUPABASE_ENVIRONMENTS.md`.

## What to do

1. Go to your PROD Supabase project's dashboard → **SQL Editor → New query**.
2. Paste the block below and click **Run**.

```sql
-- public_journal_moments: the ONLY publicly-readable table in this app. One row per moment
-- a user has explicitly chosen to make public; deleted the moment the instant it's made
-- private again (see journalSyncPublic() in index.html). Never holds anything the owner
-- hasn't explicitly opted to share.
create table if not exists public.public_journal_moments (
  id            text primary key,               -- same id as the owner's private wp-journal-moments-v1 record
  user_id       uuid not null references auth.users(id) on delete cascade,
  author        text not null default '',        -- display name snapshot at publish time (wp-user-name-v1, or an email prefix)
  type          text not null,                    -- 'photo' | 'place' | 'song' | 'movie' | 'recipe' | 'link' | 'note'
  title         text not null default '',
  description   text not null default '',
  image         text,                             -- data URL, same resizeImageJPEG pipeline as the private copy
  thumb         text,                             -- data URL, small preview — Explore's grid only ever loads this
  external_url  text,                             -- a URL string only, never fetched/mirrored content
  location      jsonb,                             -- { name, url } for type = 'place'
  artist        text,
  is_editorial  boolean not null default false,    -- true only for official @svoj seed content — see docs/EDITORIAL_SEED.md. Never rendered/exposed in any UI; purely an internal marker so editorial rows can be found/removed/excluded from future analytics as a group
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  published_at  timestamptz not null default now() -- what Explore sorts by
);

-- Safe to run even if the table already existed from before is_editorial was added — this is
-- a no-op if the column is already there.
alter table public.public_journal_moments add column if not exists is_editorial boolean not null default false;

alter table public.public_journal_moments enable row level security;

-- Anyone (including signed-out visitors) can read public moments — that's the entire point
-- of Explore. Nothing private ever lands in this table in the first place.
create policy "anyone can view public journal moments"
  on public.public_journal_moments for select
  using (true);

create policy "individuals can insert their own public journal moments"
  on public.public_journal_moments for insert
  with check (auth.uid() = user_id);

create policy "individuals can update their own public journal moments"
  on public.public_journal_moments for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "individuals can delete their own public journal moments"
  on public.public_journal_moments for delete
  using (auth.uid() = user_id);

-- Explore always queries "newest first" (order by published_at desc) filtered by user_id !=
-- me — this index covers that access pattern directly.
create index if not exists public_journal_moments_published_at_idx
  on public.public_journal_moments (published_at desc);
```

3. Confirm it worked: **Table Editor** should show a `public_journal_moments` table with 0
   rows, RLS enabled, and the index listed under the table's **Indexes** tab.

That's it — no app code changes are needed once the table exists. The very next time a user
taps **Make Public** on a moment, or opens **Explore**, it starts working.

## Do the same in DEV

If/when the DEV Supabase project from `docs/SUPABASE_ENVIRONMENTS.md` is created, run the exact
same SQL there too so DEV stays a faithful mirror of PROD's schema.

## Shareable public URL

Every public moment's own `id` (the primary key above) doubles as its shareable link's slug —
no separate slug/token column was added. The app has zero routing otherwise (see
`docs/IOS_READINESS.md`), so this is intentionally the simplest possible mechanism: a
`?moment=<id>` query param, read once at page load (`renderPublicMomentView()` in `index.html`).
When present, the ENTIRE normal app boot (auth screen, onboarding, sign-in) is skipped in favor
of a minimal read-only card showing just that one row, fetched with the anon key — this works
for a signed-out visitor because the table's own SELECT policy already allows anonymous reads.
Nothing beyond that single row is ever exposed: no other public moments, no private data, no
Explore listing. "Copy link"/"Share" in Explore and in a moment's own detail view (when public)
both just build this same URL client-side (`publicMomentUrl(id)`) — there is no server-issued
token to keep in sync.

## `is_editorial` — official SVOJ seed content

A single official `@svoj` account can publish curated Explore starter content so a brand-new
install doesn't feel empty. `is_editorial` marks those rows only — it is a plain boolean column,
not a separate table or a special account type; `@svoj` is an ordinary Supabase Auth user like
any other, subject to the exact same RLS policies above. See **docs/EDITORIAL_SEED.md** for the
full setup (creating the account, claiming the username, running the content migration).

- **Never rendered.** No UI anywhere reads or displays this column — `journalExploreCardHtml()`/
  `journalOpenExploreDetail()` only ever destructure the named fields they use (`title`,
  `description`, `type`, `author`, ...), so an extra column sitting unused in the row object is
  automatically inert. There is no "Admin"/"System"/"Seed" label anywhere; `@svoj`'s public
  moments display exactly like any other user's.
- **RLS is row-level, not column-level** — `select('*')` (which Explore already does) returns
  this column's value to the browser like any other public column. That's expected and harmless:
  it's an internal categorization flag on public data, not a secret: never treat it as something
  that needs hiding from network responses, only from the rendered UI (which it already is).
- **Why it exists:** so editorial content can later be found, bulk-updated, replaced, or removed
  with one predicate (`where is_editorial = true`), and excluded from any future analytics that
  count real user activity — without needing a special account type or a parallel content table.
- **`Save to My Journal` never copies it.** `journalSaveExploreItemToMyJournal()` builds the
  saved local copy from a fixed list of named fields and always sets `visibility:'private'` — it
  has no code path that could carry `is_editorial` (or anything else non-listed) into a real
  user's own private Journal data.

## Storage note

Like every other photo in this app (see `docs/SUPABASE_ENVIRONMENTS.md` → "Storage buckets"),
`image`/`thumb` here are plain base64 `data:` URLs in a `text` column, not Supabase Storage
objects — consistent with the app's existing "no Storage bucket" architecture, not a new one
introduced for this feature. Moving all photos (private and public) to real Storage buckets
remains a real future improvement, and should be done for both at once, not just for this table.

## What "Save to My Journal" does *not* duplicate

Saving a public moment copies its already-compressed `image`/`thumb` strings by value into the
saver's own private `wp-journal-moments-v1` row — it does not re-fetch, re-compress, or create
any new asset. That is an unavoidable full copy of the string under this table's current
architecture (no Storage bucket to reference by URL instead); switching to Storage buckets
later would let a saved copy reference the same underlying object instead of duplicating it.
