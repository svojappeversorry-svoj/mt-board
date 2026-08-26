# Project cleanup audit

> **Note:** this is a point-in-time audit from an earlier pass. The sticker feature it describes
> below (`assets/stickers/`, `BUILTIN_STICKER_PACKS`) was removed entirely in a later pass — see
> `docs/DATA_CONTRACTS.md`'s "Stickers — removed" section and `docs/TESTING_CHECKLIST.md`'s
> Journal-redesign section. The avatar count below is also stale (now 15, not 10) after a later
> replacement pass. Left as-is rather than rewritten, since this file records what was true at
> the time of that original audit.

## Repo-level files

Every file in the repository was checked for whether it's actually referenced. Result: **all of
them are.** Every avatar `.webp`, every sticker pack `.webp`, every app icon `.png`, and
`manifest.webmanifest` is referenced by name somewhere in `index.html` or the manifest itself.
There are no orphaned assets, no leftover exports from earlier redesign phases, and no stray
temp/debug files anywhere in the repo.

| Item | Classification |
|---|---|
| `index.html` | KEEP — the entire app |
| `assets/avatars/*.webp` (10 files) | KEEP — all referenced by `AVATAR_COLLECTION` |
| `assets/stickers/*/*.webp` (60 files) | KEEP — all referenced by `BUILTIN_STICKER_PACKS` |
| `icon-32.png` / `icon-180.png` / `icon-192.png` / `icon-512.png` | KEEP — favicon/PWA/App Store icon sources |
| `manifest.webmanifest` | KEEP — PWA install manifest |
| `docs/*.md` | KEEP — this preparation's own documentation |
| `_headers`, `.gitignore` | KEEP — added this session (security headers, future secret hygiene) |

## Inside `index.html`: dead code search

- **No debug `console.log` calls anywhere** — only `console.error`/`console.warn`/`console.info`
  used for genuine error reporting.
- **No leftover code from previously-removed features.** Checked specifically for remnants of
  "Daily Goals" (removed in an earlier phase) and the standalone "SVOJ Money" app (removed in an
  earlier phase, per its own commit) — none found. Past cleanups were done thoroughly.
- **No leftover old theme names.** Checked for "Petal" (Botanical's old name), "Forest Noir" and
  "Pop Scrapbook" (early internal theme names) — none found in current code (some appear only in
  historical git commit messages, which is normal and fine).
- **One trivial, genuinely duplicate CSS declaration, fixed:** `.year-view{}` was declared twice
  a few lines apart (`{ display:none; }` and, separately, `{ position:relative; }`) instead of
  once with both properties. Merged into a single declaration — **zero visual or behavioral
  change**, purely tidiness. This was the only true duplicate-selector case found across the
  whole stylesheet.
- **Dependencies:** no `package.json`, `node_modules`, or lockfile exists (the app has no build
  step by design), so there's nothing to prune there. The only external dependency is the pinned
  `@supabase/supabase-js@2.112.4` CDN `<script>` tag — already addressed in the earlier
  preparation pass.

## SAFE TO REMOVE

Nothing. There was nothing in the repository or the code that was unused, obsolete, or safe to
delete beyond the one trivial CSS merge above (already applied).

## NEEDS REVIEW (not removed — a product decision, not a cleanup)

- **Sticker pack internal ids don't match current theme names** (`y2k-vixen` for Pink Pop,
  `petal-botanical` for Botanical) — documented in detail in `docs/THEME_ARCHITECTURE.md`.
  Deliberately not renamed: doing so would silently break any sticker a real user has already
  placed, since those ids are saved inside their `wp-stickerzones-v5` data. Needs a real data
  migration if it's ever addressed, not a quick rename.

## KEEP

Everything else — the codebase is small enough (one file, no framework, no build artifacts) and
has been maintained carefully enough across its history that there simply isn't a backlog of
cruft to work through. This is a good sign for the iOS preparation work ahead: there's no hidden
technical debt lurking that would need cleaning up before it can be safely used as a reference for
a native/Capacitor rebuild.
