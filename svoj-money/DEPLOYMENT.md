# SVOJ Money — independence & data-isolation fix

## Root cause (why Account B could see Account A's data)

Three separate issues, all confirmed by reading the shipped source in
`svojmoneystandalone.zip` / `expenses.html` before any change was made:

1. **SVOJ Money and the SVOJ planner app shared one Supabase project.**
   The code said so directly: *"Same Supabase project + save()/load()
   pattern as the main SVOJ app... Same account/session as the main SVOJ
   app, so logging in here logs into the exact same account."* Both apps
   used the same `auth.users`, the same `app_data` table, and the same
   `wp-*` data keys. Deploying Money to its own Netlify domain changed
   nothing about this — the backend was never split, only the frontend was.

2. **Every brand-new account was auto-seeded with 22 hardcoded "Montenegro
   trip" demo expenses** (`seedInitialExpenses()`), totalling ~€3,558,
   tagged `"shared"`. Any two unrelated new accounts ended up with
   *identical* fake transactions — indistinguishable, from the UI, from one
   account's real data "leaking" into another.

3. **Signing out never cleared local expense data.** `handleLogout()` only
   removed the offline-mode flag, not the actual cached expenses/income in
   `localStorage`. On a shared or reused device/browser, the next person to
   sign in — or the next person to tap "continue without an account" —
   would inherit the previous account's financial data before the cloud
   fetch even ran, and it could get permanently written into their own
   cloud account by the local→cloud migration step.

There was also real (non-seed) logic hardcoded to `"eva"`/`"mark"`/`"shared"`
in the calendar day view and the category-budget breakdown — not itself a
cross-account leak, but exactly the kind of hardcoding the isolation work
needed to remove, since it assumed a fixed two-person household.

Root cause of "why didn't the new domain fix it": a Netlify domain only
changes where the *static files* are served from. `localStorage` is already
origin-scoped by the browser, so it was never actually shared between the
two domains. What *is* still shared across any number of frontend domains is
the **backend** — one Supabase project, one `auth.users` table, one
`app_data` table — and that's what needed to change.

## What changed (in `svoj-money/index.html`)

- Removed the 22-expense hardcoded seed and its supporting dedup logic —
  `defaultData()` now starts completely empty for every account.
- Removed the `eva`/`mark`/`shared` hardcoded-people migration fallback —
  every account (new or old) now starts with exactly one person, "you".
- Added a one-time onboarding prompt ("What should we call you?") that
  renames that one default person — no account is ever pre-populated with
  named participants.
- Rewrote the calendar day-detail widget and the category-budget breakdown
  to iterate `DB.settings.people` dynamically instead of checking
  `e.user === "eva"` / `"mark"` / `"shared"`. (The dashboard split and the
  stats "compare by person" widget were already dynamic — only these two
  spots still had the old hardcoding.)
- Renamed every `wp-*` localStorage/cloud key to `svojmoney-*`, and rewrote
  every comment that described this app as sharing an account, a Supabase
  project, or storage with "the main SVOJ app."
- **`handleLogout()` now clears all local expense/income/settings data**
  (not just the offline flag) before signing out — this is the fix for leak
  #3 above.
- Renamed the single app-accent color setting from the confusing
  `userColors.eva` / `#color-eva` to `userColors.accent` / `#color-accent`,
  and deleted the now-fully-dead `--eva-*`/`--mark-*`/`--shared-*` CSS.
  (Per-person tag colors were already a separate, already-dynamic system —
  `DB.settings.people[].color` — untouched.)
- Replaced the Supabase URL/anon key with placeholders you fill in once you
  create the new project below.
- Fixed a pre-existing, unrelated bug found during the audit: the PWA
  manifest `<link>` pointed at `money-manifest.webmanifest`, but the shipped
  zip contained a file named plain `manifest.webmanifest` — meaning the PWA
  manifest 404'd on the live site. Renamed the file to match.

Everything else — expenses, income, categories, history, statistics,
budgets, currencies, shared budgets, invitation codes, the visual design —
is unchanged.

## Architecture: what you need to create

**A separate Supabase project for SVOJ Money**, per your stated preference
for the safest option, and because the two apps' code was written assuming
one shared project — untangling that safely, with confidence, from outside
without direct access to your existing project's dashboard/RLS state,
is far riskier than starting clean. A new project also means every table,
policy, and function is defined once, from scratch, correctly — nothing
inherited or half-migrated.

You do **not** need: a different Netlify site (your existing Money domain
is fine), a different GitHub repo, or a different domain. You only need a
new Supabase project plus the two config values pasted into `index.html`.

```
SVOJ Planner  ---->  its own Supabase project (unchanged, untouched)
SVOJ Money    ---->  a brand-new Supabase project (created below)
```

No code in this app calls the planner's project, ever, again.

## Deployment steps

1. **Create the new Supabase project.**
   Go to https://supabase.com/dashboard → New project. Pick any name/region
   (e.g. "svoj-money-prod"). Wait for it to finish provisioning.

2. **Run the schema.**
   Open the new project → SQL Editor → New query. Paste the entire contents
   of `svoj-money/supabase/schema.sql` (in this repo) and click Run. This
   creates every table, RLS policy, and function needed — including the
   shared-budget invite-code system — in one pass. It's safe to re-run if
   something fails partway (uses `create table if not exists` /
   `create or replace function`).

3. **Copy your API credentials.**
   In the new project: Project Settings → API. Copy the **Project URL** and
   the **`anon` `public`** key (not the `service_role` key — never put that
   in client-side code).

4. **Paste them into the app.**
   Open `svoj-money/index.html`, find:
   ```js
   const SUPABASE_URL = 'PASTE_YOUR_SVOJ_MONEY_SUPABASE_URL_HERE';
   const SUPABASE_ANON_KEY = 'PASTE_YOUR_SVOJ_MONEY_SUPABASE_ANON_KEY_HERE';
   ```
   and replace both placeholder strings.

5. **Enable email confirmation the way you want it.**
   In the new project: Authentication → Providers → Email. Decide whether
   you want signup email confirmation on (safer, adds a step) or off
   (faster onboarding) — this is independent of anything above.

6. **Deploy the files.**
   The whole `svoj-money/` folder (`index.html`, the four `money-icon-*.png`
   files, `money-manifest.webmanifest`) is what gets deployed — the
   `supabase/` folder is documentation/tooling only and doesn't need to be
   uploaded to Netlify. Your existing Netlify site for SVOJ Money can stay
   exactly where it is:
   - Drag-and-drop deploy: drag the `svoj-money/` folder contents onto
     Netlify's deploy page (or your site's "Deploys" tab).
   - Or connect this GitHub repo to that Netlify site with the base
     directory set to `svoj-money/` (publish directory `svoj-money/`, no
     build command needed — it's static files).

7. **Hard-refresh the live site once** after deploying (or open it in a
   private window) so no browser has the old build cached.

## Test plan

Run these in order, using two different email addresses for "Account A" and
"Account B" (or two browser profiles/private windows if you want to test
same-device isolation too).

| # | Step | Expected result |
|---|------|------------------|
| 1 | Sign up as Account A, add a €100 expense, log out | Logout succeeds, returns to the auth screen |
| 2 | Sign up as Account B (same device/browser is fine now) | App starts **completely empty** — no expenses, no €100, no old totals, no pre-set people beyond the one "what should we call you?" prompt |
| 3 | Account B adds a €200 expense, logs out | — |
| 4 | Log back into Account A | Sees **only** its own €100 expense — nothing from B |
| 5 | Account A creates a shared budget (Settings → Shared budget → Create), copy the invite code | — |
| 6 | Account B joins with that code | Both accounts now see the shared budget and each other's shared-budget entries |
| 7 | In the shared budget, Account A adds a *personal* (non-common) entry | — |
| 8 | Account B opens the shared budget | Sees Account A's entry (with A's name) but the entry is **not clickable/editable** for B (no delete/edit affordance — enforced by the `owner_id = auth.uid() OR is_common` RLS policy, not just hidden by the UI) |
| 9 | Repeat 7–8 in reverse (B posts personal, A can't edit it) | Same result, symmetric |
| 10 | Open the app fresh on a different browser/device, sign up a third account | Starts completely empty, same as step 2 |
| 11 | Check for any planner data anywhere in Money (dashboard, history, categories) | None — the two apps no longer share a backend at all |

Steps 1–4 and 10–11 are the ones that directly re-test the original bug
report. Steps 5–9 confirm the shared-budget permission model (own data
editable, common data editable by any member, another member's personal
data never editable) survives the migration to the isolated schema.

## What you need to do manually

Everything above requires your own Supabase account (project creation,
running the SQL, copying keys) and your own Netlify account (deploying the
`svoj-money/` folder) — neither can be done on your behalf without your
credentials. Steps 1–7 are the full manual checklist; nothing else is
required on your end.
