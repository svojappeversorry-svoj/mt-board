# SVOJ documentation

Prepared ahead of iOS/App Store development. Start here.

## If you're picking this back up after creating the DEV Supabase project

Go straight to **[SUPABASE_ENVIRONMENTS.md](./SUPABASE_ENVIRONMENTS.md)** — its checklist at the
bottom says exactly what to confirm before iOS work begins.

## Full document list

| Doc | What's in it |
|---|---|
| [DATA_CONTRACTS.md](./DATA_CONTRACTS.md) | Every `app_data.data_key` the Web app uses — exact JSON shape, types, defaults, how it's read/written. The contract a future iOS client must match. |
| [SUPABASE_ENVIRONMENTS.md](./SUPABASE_ENVIRONMENTS.md) | Which Supabase project is PROD vs. DEV, manual dashboard steps + SQL to create DEV, a "what done looks like" checklist. |
| [SECURITY.md](./SECURITY.md) | 20-point security checklist against the real code, with priorities and what's already fixed vs. still open. |
| [IOS_READINESS.md](./IOS_READINESS.md) | Photos/camera, file storage, auth, deep links, notifications, local storage, offline mode, network handling — what's reusable vs. needs native/Capacitor work. |
| [THEME_ARCHITECTURE.md](./THEME_ARCHITECTURE.md) | How the 4-theme system is actually built, what's genuinely extensible, and the two small naming inconsistencies found (one fixed, one deliberately left alone). |
| [PROJECT_CLEANUP.md](./PROJECT_CLEANUP.md) | What was checked for unused files/dead code, and the one trivial fix made. |
| [TESTING_CHECKLIST.md](./TESTING_CHECKLIST.md) | What was verified in this pass and how to re-run the same checks later. |

## The one-paragraph summary

The Web app (`index.html`) is unchanged in behavior — every edit in this pass was either a pure
documentation update, a one-line dependency version pin, or a small, safe, local bug fix (content
escaping, a hung upload promise, a mislabeled sticker pack, a trivial CSS duplicate, a stricter
password minimum). Nothing touches Supabase, no schema changed anywhere, and PROD was never
connected to from this session. The DEV Supabase project doesn't exist yet — creating it is the
one remaining manual step, and everything needed to do that quickly and correctly is in
`SUPABASE_ENVIRONMENTS.md`.
