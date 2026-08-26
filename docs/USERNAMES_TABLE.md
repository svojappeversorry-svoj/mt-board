# Usernames — the `usernames` table

This is a **required manual step**, not an optional one: until this table exists in the PROD
Supabase project, saving a username in My Profile still works locally (and for that account's
own Journal) but **cannot verify global uniqueness** — the app falls back to "can't verify right
now" and saves it anyway, logging a console warning. Once the table exists, uniqueness is
enforced for real, both by a client-side availability check and by the table's own primary key
(so two people racing to claim the same name can never both succeed).

## Why a new table, and why this session can't create it

Same reasoning as `public_journal_moments` (see `docs/JOURNAL_PUBLIC_TABLE.md`): every other
piece of user data lives in `app_data`, whose row-level security is "the owner can read/write
their own row only" — that can never answer "does anyone else already have this username".
Checking uniqueness needs a table anyone can `select` from, which is a schema change against
your real Supabase project. This session only holds the client-side anon key — running SQL
requires your Supabase dashboard, same limitation documented in `docs/SUPABASE_ENVIRONMENTS.md`.

## What to do

1. Go to your PROD Supabase project's dashboard → **SQL Editor → New query**.
2. Paste the block below and click **Run**.

```sql
-- usernames: the public @handle every account claims once. Publicly readable (so anyone can
-- check availability, and a stranger's client can resolve "whose moment is this" from a public
-- moment's author), but only the owner can claim/change/release their own row. This table does
-- NOT duplicate profile data — the canonical value still lives in the owner's own wp-username-v1
-- (synced via the normal app_data mechanism); this table exists only to enforce global
-- uniqueness and make the handle resolvable by other people's clients.
create table if not exists public.usernames (
  username    text primary key,                 -- lowercase, no leading "@" — the app adds
                                                   -- the "@" only when displaying it
  user_id     uuid not null unique references auth.users(id) on delete cascade,
  created_at  timestamptz not null default now()
);

alter table public.usernames enable row level security;

-- Anyone (including signed-out visitors) can look up a username — needed both for the
-- availability check during onboarding/Settings, and so a public moment's author can be
-- resolved without exposing anything else about that account.
create policy "anyone can view usernames"
  on public.usernames for select
  using (true);

create policy "individuals can claim their own username"
  on public.usernames for insert
  with check (auth.uid() = user_id);

-- Changing your username later is an update (not delete+insert) so the client can use a single
-- upsert keyed on user_id — the unique(user_id) constraint above means this always targets that
-- one account's row, and it will still fail if the NEW name collides with someone else's
-- primary key (username), so a rename can't accidentally steal a taken handle either.
create policy "individuals can update their own username"
  on public.usernames for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "individuals can delete their own username"
  on public.usernames for delete
  using (auth.uid() = user_id);
```

3. Confirm it worked: **Table Editor** should show a `usernames` table with 0 rows, RLS enabled.

That's it — no app code changes are needed once the table exists. The very next username saved
from onboarding or My Profile will be checked and claimed for real.

## Do the same in DEV

If/when the DEV Supabase project from `docs/SUPABASE_ENVIRONMENTS.md` is created, run the exact
same SQL there too so DEV stays a faithful mirror of PROD's schema.

## What happens to public content published before a username existed

`public_journal_moments.author` for any moment published before this feature snapshotted a real
name or email prefix at publish time (see `docs/JOURNAL_PUBLIC_TABLE.md`) — those existing rows
are **not** retroactively rewritten by this change. Every *new* publish (or re-publish/edit of an
existing public moment) now snapshots the current `@username` (or the neutral `SVOJ member`
placeholder if the account still hasn't claimed one) instead. If closing that old-data gap
matters, it would need a one-time backfill script run against PROD directly — not something this
session can do without dashboard/service-role access.
