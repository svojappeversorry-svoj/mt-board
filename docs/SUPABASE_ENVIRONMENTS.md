# Supabase environments — PROD vs DEV

This file is the single source of truth for which Supabase project is which. Keep it up to
date whenever an environment changes.

## PROD (live, real users — do not touch)

- **Used by:** the live SVOJ Web app on Netlify (`index.html`, `SUPABASE_URL`/`SUPABASE_ANON_KEY`
  constants near the top of the inline `<script>`).
- **Project URL:** `https://cdvvpkpbqkxxyytphjht.supabase.co`
- **Contains:** real user accounts, real Web user data (days, photos, expenses, themes,
  everything under the `app_data` table).
- **Rule:** nothing done for iOS/dev preparation should ever run against this project's SQL
  editor, its Auth users list, or its table data. `index.html` keeps pointing at it, unchanged.

## DEV (for iOS development and testing — safe to experiment on)

- **Status as of this document: not created yet.** Creating a Supabase project requires an
  account action in the Supabase dashboard that this session cannot perform on your behalf —
  see "What you need to do" below.
- **Will be used by:** the future iOS/Capacitor codebase during development, and by any local
  testing of new data-layer code, so real Web user data is never at risk.
- **Project URL:** _TODO — paste here once created_
- **Anon public key:** _TODO — paste here once created (safe to store in a client app/this repo;
  it is a public, RLS-restricted key, the same kind already hardcoded in `index.html` for PROD)_
- **Contains:** only test/development data you create yourself.

`index.html` is **not** changed by this preparation — it keeps using PROD directly, exactly as
today. The DEV project's credentials only need to exist somewhere the future iOS codebase reads
from (e.g. its own config file) once that codebase is started; there is nothing to wire up here
yet.

---

## What you need to do (manual, in the Supabase dashboard)

I can't create a Supabase project, run SQL against your account, or generate API keys for you —
none of that is reachable from this session. Here's exactly what to click, in order:

### 1. Create the project

1. Go to <https://supabase.com/dashboard> and sign in (same account as PROD, or a separate one —
   either works).
2. Click **New project**.
3. Pick the same organization as PROD (or a new one if you'd rather keep it fully separate).
4. Name it something unambiguous, e.g. `svoj-dev` or `SVOJ (Development)`.
5. Set a database password and **save it somewhere safe** (a password manager). `index.html`
   never needs this password — it only uses the anon key below — but you'll want it if you ever
   need to connect a SQL client directly.
6. Pick the region closest to you and click **Create new project**. Provisioning takes ~1–2
   minutes.

### 2. Copy the API credentials

1. Once the project is ready, go to **Project Settings → API** (some dashboard versions call
   this **Data API**).
2. Copy the **Project URL** and the **anon public** key.
3. Paste both into the "DEV" section above in this file, replacing the `TODO` placeholders.

### 3. Recreate the `app_data` table and its security rules

The current PROD schema isn't exported anywhere in this repository (it only exists in the PROD
project's dashboard), so this SQL was written directly from how `index.html`'s code actually
calls Supabase (`sb.from('app_data').select(...)`, `.upsert(..., { onConflict: 'user_id,data_key' })`,
`.delete()`) — it reproduces exactly the table shape and row-level security the app depends on.

1. In the **new DEV project**, open **SQL Editor → New query**.
2. Paste the block below and click **Run**.

```sql
-- app_data: the single generic key-value store table the SVOJ Web app uses for every
-- persisted user record (theme, days, photos, expenses, settings, ...). One row per
-- (user_id, data_key) pair; "data" holds that key's whole JSON payload.
create table if not exists public.app_data (
  user_id    uuid not null references auth.users(id) on delete cascade,
  data_key   text not null,
  data       jsonb,
  updated_at timestamptz not null default now(),
  primary key (user_id, data_key)
);

alter table public.app_data enable row level security;

create policy "individuals can view their own app_data"
  on public.app_data for select
  using (auth.uid() = user_id);

create policy "individuals can insert their own app_data"
  on public.app_data for insert
  with check (auth.uid() = user_id);

create policy "individuals can update their own app_data"
  on public.app_data for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "individuals can delete their own app_data"
  on public.app_data for delete
  using (auth.uid() = user_id);
```

3. Confirm it worked: **Table Editor** should now show an `app_data` table with 0 rows, and its
   RLS toggle should show "Enabled".

> **Please double-check PROD has the equivalent RLS policies.** They aren't visible from the
> code or this repository — only from the PROD project's own dashboard
> (**Authentication → Policies**, or **Table Editor → app_data → RLS**). This audit assumes they
> exist (the app's whole security model depends on them), but it's worth a quick look since nothing
> in the codebase can confirm it either way.

### 4. Check Auth settings match what you expect

1. Go to **Authentication → Providers** and confirm **Email** is enabled (it is by default).
2. Go to **Authentication → Settings** (sometimes under **Authentication → Providers → Email**)
   and check the **Confirm email** toggle. The Web app's sign-up flow shows a "check your email"
   message either way, but if you want DEV to behave identically to PROD for testing, compare
   this toggle's value against your PROD project's Authentication settings and match it.

### 5. (Optional) Create one or two test accounts

Either sign up normally through a future test client once it exists, or create them directly:
**Authentication → Users → Add user**. This gives you a ready-made account to test against
before any iOS code exists.

---

## Why this separation matters

Without a separate project, any iOS-side experiment (signing up test users, writing malformed
`data_key` payloads while the Swift-side reader is still being built, running bulk test data
scripts) would land in the exact same `app_data` table your real Web users' rows live in. The DEV
project gives iOS development a completely isolated place to break things safely.
