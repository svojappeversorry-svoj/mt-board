# Security audit

Checked against the actual code and git history, with the future iOS app in mind. Legend:
✅ already safe · ⚠️ needs verification · ❌ needs implementation · ➖ not applicable.

## 1. Hide API keys — ✅ Already safe
`SUPABASE_URL` and the **anon/public** key are hardcoded in `index.html`, visible to anyone who
views the page source. This is correct, not a leak: Supabase's anon key is *designed* to be
public and is meaningless without matching row-level-security policies doing the actual access
control (see #4). Checked specifically for anything stronger — no `service_role` key exists
anywhere in the current code.

## 2. Purge Git secrets — ✅ Already safe
Searched the full git history (all 49 commits, every branch) for `.env` files, `service_role`,
common secret-key patterns, and any JWT-shaped string. The **only** JWT-shaped string ever
committed is the one anon key above — decoded, its payload confirms `"role":"anon"`. Nothing
sensitive has ever leaked into this repo.

## 3. Use public DB key — ✅ Already safe
Confirmed: the client only ever holds the anon key. No code path constructs or references a
`service_role` key.

## 4. Enable row-level security — ⚠️ Needs verification
The app's entire security model depends on RLS existing on PROD's `app_data` table (every query
is a plain `select`/`upsert`/`delete` with no other access control in the client). **This can't be
confirmed from the code or this repository** — RLS policies live only in the PROD Supabase
dashboard, which this session was explicitly told not to touch. Please check **PROD dashboard →
Authentication → Policies** (or **Table Editor → app_data → RLS**) confirms RLS is enabled with
policies restricting every operation to `auth.uid() = user_id`. The DEV project's prepared SQL
(`docs/SUPABASE_ENVIRONMENTS.md`) already includes the correct policies from day one.

## 5. Encrypt sensitive data — ✅ Already safe / ➖ not applicable beyond this
Supabase's managed Postgres encrypts data at rest by default — this covers everything in
`app_data` (including budget/expense figures) with no app-level work needed. Nothing currently
stored (mood, sleep, water, notes, expense amounts) rises to a sensitivity level (medical records,
government IDs, card numbers) that would need additional field-level encryption on top of that.
Revisit only if a future feature stores something in that higher-sensitivity category.

## 6. Enforce server-side auth — ⚠️ Needs verification (same root cause as #4)
There is no custom backend — Supabase Auth *is* the server-side authority on who's signed in, and
RLS is the server-side authority on what they can touch. Both are correctly designed into how the
client calls Supabase; whether they're actually *turned on* in PROD is the same open question as
#4.

## 7. Lock record access — ⚠️ Needs verification (same as #4/#6)
Every `app_data` row should only be readable/writable by the `user_id` it belongs to. The client
already always filters by `currentUserId` (the signed-in session's own id, never user-editable
input) — but that's a courtesy, not a security boundary. The real boundary is RLS.

## 8. Block field tampering — ⚠️ Needs verification (same as #4)
A signed-in user with dev tools open could, in principle, call the Supabase REST API directly
with a `user_id` in the payload that *isn't* their own. The client-side code never does this, but
nothing client-side can prevent someone from trying — RLS's `with check (auth.uid() = user_id)`
on insert/update is the only thing that actually blocks it. Already included in the DEV setup SQL.

## 9. Secure session handling — ✅ Already safe, with one relevant connection to #15
Session handling is entirely the Supabase JS SDK's own default behavior (JWT persisted in
`localStorage`, refreshed automatically) — nothing custom or weakened. `signOut()` is followed by
`location.reload()`, which fully clears in-memory state (`cloudCache`, etc.) rather than leaving
stale signed-in data around. Worth knowing: because the session token lives in `localStorage`, a
successful XSS *would* be able to read it — which is the real reason the escaping fixes in #15
matter beyond just "ugly rendering."

## 10. Password security — ⚠️ Needs verification, partially fixed
The client-side minimum was 6 characters (Supabase Auth's historic default) on both sign-up and
change-password — raised to **8 characters** in this pass (three spots: the sign-up check, the
change-password check, and both user-facing "needs N+ characters" messages, kept consistent).
This is a pure client-side tightening — it can only reject more weak passwords than before, never
fewer, so it can't break any existing account. **Still worth checking** PROD's dashboard
(**Authentication → Policies/Settings → minimum password length**) to confirm the *server* also
enforces at least this much, independent of the client.

## 11. Login rate limiting — ➖ Not applicable to app code
Supabase's Auth service (GoTrue) applies its own rate limits to sign-up/sign-in/OTP endpoints by
default — this isn't something `index.html` implements or could weaken. If you want to double
check current limits, that's a PROD dashboard setting, not a code question.

## 12. Bot protection — ❌ Needs implementation (optional, low priority for now)
No CAPTCHA/Turnstile is wired into the sign-up form. Supabase Auth supports optional CAPTCHA
integration, but it requires both a dashboard toggle and a small code change to render the
challenge widget — neither exists today. Given current usage scale, this is reasonable to defer;
worth reconsidering if/when the App Store listing drives meaningfully more sign-up traffic.

## 13. Parameterized queries — ✅ Already safe
Every single database call goes through the Supabase JS query builder
(`.from().select()/.upsert()/.delete()`) — there is no raw SQL string concatenation anywhere in
the client. This class of vulnerability structurally can't occur here.

## 14. Input validation — ⚠️ Needs verification / partial
Client-side validation exists for the obvious cases (email+password presence, expense amount
`parseFloat`), but there's no schema validation preventing a signed-in user from writing
oddly-shaped data to their *own* `app_data` rows via a direct API call. Because RLS (once
confirmed) scopes every row to its owner, the realistic worst case is a user corrupting their own
data, not affecting anyone else's — this keeps it at a lower priority than the RLS items above.
Not fixed in this pass (would mean adding real validation logic, which is more than a "safe local"
change) — worth scoping deliberately later if it becomes a real problem.

## 15. User-content escaping — ❌ Found and fixed
Found **6 places** where user-typed text was interpolated into `innerHTML` without the
`.replace(/</g,'&lt;')` escaping already used consistently everywhere else in the codebase — an
inconsistency, not a systemic gap (the *pattern* clearly exists and is used correctly dozens of
times; these six spots simply missed it):

1. Month notes textarea (`monthNotes`)
2. Day notes textarea (`dd.notes`)
3. Generic text-widget textarea (`dayVal`)
4. Attached vibe pills display (`vibeLabel(v)`) — was escaped in the *picker* one line away, not
   in the pill itself
5. Monthly Recap card's category label (`c.label`) — was escaped correctly in the main Favorites
   list, not in this second render of the same value
6. The "reorder enabled widgets" list's custom-widget name (`def.label`) — was escaped correctly
   in the "manage custom widgets" card, not in this sibling list

The realistic risk given the app's shape today: this is a **self-XSS** (you'd have to type/paste
malicious markup into your own notes/labels and then view it back), with no cross-user exposure
since every user's data is already isolated by `user_id`. It's still worth having fixed, both on
general principle and because of #9 (a successful self-XSS can read your own session token from
`localStorage`) — and because it's the kind of thing App Store/security reviewers do look for.
**Fixed** — all six now use the same escaping already used elsewhere in the file; zero visual or
behavioral change for any normal (non-`<`-containing) text.

## 16. File upload restrictions — ⚠️ Needs verification, one bug fixed
`accept="image/*"` on file inputs is a UI hint only, not an enforced restriction — nothing stops
a differently-typed file from being selected. Checked the actual impact: images are read via
`FileReader` → drawn to a `<canvas>` → re-encoded, so a non-image file simply fails to decode; it
is never executed or trusted as anything other than pixel data. One real bug found and fixed:
`resizeImagePNG()` (used for custom sticker uploads) had no `onerror` handler, unlike its sibling
`resizeImageJPEG()` — selecting a corrupt/non-image file left that upload's `await` hanging
**forever**, silently breaking the sticker-upload flow for the rest of that session. Fixed to
resolve `null` on failure (matching the JPEG path's behavior) and the caller now skips `null`
results instead of pushing a broken entry. No size limit exists before reading a selected file
into memory — a very large file could make one browser tab slow/unresponsive during that read,
but never reaches Supabase (only the small resized output is ever saved), so this is a UX
robustness gap, not a security one. Not fixed in this pass; low priority.

## 17. API response minimization — ✅ Already safe
The one and only `select()` call in the app already scopes its columns explicitly
(`select('data_key, data')`) rather than `select('*')`, even though it also filters by `user_id`.
No over-fetching found anywhere.

## 18. Security headers — ❌ Found and fixed (partially)
No headers were configured at all (no `netlify.toml`, no `_headers` file existed). Added a
`_headers` file at the repo root (Netlify reads this automatically, no build step needed) with
`X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`,
`X-Frame-Options: SAMEORIGIN`, and a `Permissions-Policy` blocking camera/microphone/geolocation
(none of which the app uses today). **Deliberately did not add a Content-Security-Policy** — this
app loads from several different origins (jsdelivr, Google Fonts, Supabase, two currency-rate
APIs), and a CSP needs to be built and tested against all of them together to avoid silently
breaking the app; guessing at one here would risk exactly the kind of Web-breaking change this
preparation pass was told to avoid. Worth doing as its own deliberate, tested task.

## 19. HTTPS — ✅ Already safe
Netlify serves everything over HTTPS by default and this isn't something the app could
misconfigure. Every external resource the app loads (Supabase, jsdelivr, Google Fonts, the two
currency APIs) is also `https://`.

## 20. Dependency vulnerability scanning — ✅ Already safe (verified, not just assumed)
There's no `package.json`/lockfile to run a normal `npm audit` against — the only real dependency
is the pinned `@supabase/supabase-js@2.112.4` CDN script. Queried npm's own audit endpoint
directly against that exact version: **zero known vulnerabilities** (critical/high/moderate/low/
info all report 0). Nothing else in the project has a "version" to scan — Google Fonts and the
currency-rate APIs are consumed as plain URLs/JSON, not versioned code dependencies.

---

## Priority summary

| Priority | Items |
|---|---|
| **CRITICAL** | none found |
| **HIGH** | #4/#6/#7/#8 — RLS verification on PROD (can't be checked from code; please verify in the PROD dashboard when convenient) |
| **MEDIUM** | #15 (fixed), #10 (fixed), #18 (partially fixed — CSP still open), #16 (bug fixed, size-limit still open) |
| **LOW** | #12 (bot protection), #14 (deeper input validation) |
| **Verified clean, no action needed** | #1, #2, #3, #5, #9, #11, #13, #17, #19, #20 |

## What's fixable now vs. needs DEV Supabase vs. needs iOS work

- **Fixable now, at the repo level (done in this pass):** escaping (#15), password minimum
  (#10), the sticker-upload hang (#16), security headers (#18, partial).
- **Needs the PROD dashboard specifically (can't be done from this repo at all):** confirming RLS
  is actually enabled and correctly scoped (#4/#6/#7/#8), confirming Auth's own password-length
  and rate-limit settings (#10/#11).
- **Needs the DEV Supabase project to exist:** nothing security-specific — the DEV project's SQL
  already has correct RLS from the start (`docs/SUPABASE_ENVIRONMENTS.md`), so there's no DEV
  action item here beyond creating it.
- **Needs iOS-specific work later:** Info.plist permission-usage strings for photo library/camera
  access (there's currently no permission-request code at all because browsers don't need it —
  see `docs/IOS_READINESS.md`), and a privacy manifest/policy for App Store submission (see the
  original iOS audit).
