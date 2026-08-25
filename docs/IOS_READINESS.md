# iOS readiness — focused pass

This is a targeted follow-up to the full iOS audit (delivered earlier as a PDF/artifact), zoomed
in on the specific areas requested: what's reusable, what needs adaptation, where browser-only
logic exists, and what would need Capacitor plugins or native code. Nothing here is implemented —
this is requirements and blockers only.

## Quick reference: reuse vs. adapt vs. rewrite

| Area | Verdict | Why |
|---|---|---|
| Business logic (dates, budget math, mood/water/sleep rules) | **Reuse** | Plain JS functions, no DOM/browser API involved |
| Data shapes (`app_data` contract) | **Reuse** | Already documented in `docs/DATA_CONTRACTS.md`; platform-neutral JSON |
| Supabase Auth + `app_data` calls | **Reuse** | Same REST calls a Capacitor WebView makes today, or the same shapes a native Swift client would send |
| Photos / stickers (storage format) | **Reuse** | Plain base64 in JSON; readable/writable from any platform |
| All rendering (HTML/CSS/`innerHTML`) | **Rewrite (if native) / Reuse (if Capacitor)** | See "Two very different meanings of 'iOS'" below |
| File picking (`<input type="file">`) | **Adapt** | Works inside a WebView; a native rewrite needs `PHPickerViewController` |
| `localStorage` | **Adapt** | Concept doesn't exist in native Swift; Capacitor's WebView still has it |
| `navigator.onLine` | **Adapt** | Works in a WebView; native needs `NWPathMonitor` |

## Two very different meanings of "iOS" for this checklist

Several answers below depend entirely on which path gets picked (see the earlier audit's
section 13 for the full comparison): a **Capacitor** app still runs this exact `index.html`
inside a native WebView, so most "browser-specific logic" below simply keeps working unmodified
and only needs a native **plugin** bridged in for the handful of things a WebView genuinely can't
do (camera, real file access, push notifications). A **fully native SwiftUI** app has none of
that WebView underneath it, so every item below becomes a from-scratch native implementation. The
notes below call out both.

---

## Photos

- **Today:** `<input type="file" accept="image/*" multiple>`, read via `FileReader`, resized on a
  `<canvas>`, stored as a base64 JPEG inside `wp-photos-v1` (see Data Contracts). No Supabase
  Storage, no upload step at all — the "upload" is just a local write to `app_data`.
- **Capacitor path:** the same `<input type="file">` already opens the native photo
  picker/camera chooser on iOS inside a WebView with zero extra code — this is likely to just
  work as-is. Capacitor's `@capacitor/camera` plugin is only needed for a *richer* native picker
  UI or for camera capture with more control than the browser default gives.
- **Native path:** needs `PHPickerViewController` (or `UIImagePickerController`) wired to the
  same resize-then-base64-then-`app_data` flow, or a decision to finally move to Supabase Storage
  at that point.
- **Blocker for either path:** none today — the current 20-photos-per-day cap and client-side
  resize logic transfer conceptually as-is.

## Camera / photo library access

- **Today:** no `getUserMedia()` or camera API calls anywhere in the code — the file input's
  "camera" option (on mobile browsers) is the OS's own doing, not app code.
- **Native/Capacitor requirement:** iOS requires an explicit permission prompt with a
  human-readable reason string in `Info.plist` (`NSPhotoLibraryUsageDescription`, and
  `NSCameraUsageDescription` if camera capture is ever added) — there is currently **nothing** in
  the app that requests or handles a permission denial, because browsers don't require this
  dance. This has to be built new regardless of path chosen, including the "user said no, now
  what" UI state.

## File storage

- **Today:** `localStorage` (offline fallback + always-on write) + Supabase `app_data` (cloud).
  No file-system access at all — no downloads folder, no local file writes beyond `localStorage`.
- **The one native filesystem interaction that exists:** "Export SVOJ" (Settings) builds a
  `Blob` and triggers `<a download>` — a **browser-only** mechanism. Inside a Capacitor WebView
  this either silently fails or behaves inconsistently depending on iOS WebKit version; it needs
  `@capacitor/filesystem` + `@capacitor/share` to save/share the exported JSON properly. A native
  rewrite would use `UIActivityViewController`.
- **Blocker:** none for the rest of the app; this one specific feature needs a plugin/rewrite
  before it's meaningful on iOS — flag it, don't block everything else on it.

## Authentication

- **Today:** Supabase Auth, email+password only (`signUp`/`signInWithPassword`/`signOut`/
  `onAuthStateChange`/`getSession`), session persisted by the SDK itself (in `localStorage` in a
  browser context).
- **Capacitor path:** works unmodified — same JS SDK, same calls, inside the WebView.
- **Native path:** the official `supabase-swift` SDK exposes the same operations; this is a
  straight reimplementation of the same 5 calls in Swift, not a redesign.
- **Nothing here needs Apple's "Sign in with Apple"** unless a social/OAuth login is ever added —
  see the original audit's section 8 for why plain email+password doesn't currently trigger that
  requirement.

## Deep links / universal links

- **Today:** **none exist.** No `history.pushState`, no hash routes, no URL scheme of any kind —
  the whole app is one URL, navigation is JS show/hide of DOM containers (`show*View()` /
  `hideAllViews()` — 10 view functions total).
- **Consequence:** there is nothing to "port" here, which is good news — it means adding deep
  links (e.g. "open My Day for a specific date") is a **net-new feature** to design later, not a
  migration risk. Not a blocker for anything.

## External links (general)

- **Today:** zero external `<a href>` links or `window.open()` calls anywhere in the app.
- **For a Capacitor app:** any future external link should open via `@capacitor/browser`'s
  in-app browser rather than a bare `<a>`, so it doesn't hand the whole app off to Safari.

## Future: Spotify integration

- **Today:** does not exist in any form — no Spotify SDK, API call, or UI reference anywhere in
  the code. This is a **from-scratch feature**, not something to migrate.
- **What it would actually need later:** Spotify's iOS SDK (native) or their Web API (OAuth,
  works from a WebView too) — either is compatible with either iOS path, so this doesn't push the
  Capacitor-vs-native decision either way. Note for whenever it's built: Spotify's OAuth requires
  a registered redirect URI, which does interact with the deep-link setup above once both exist.

## Future: Instagram links

- **Today:** does not exist. Same as Spotify — a net-new feature, no migration risk.
- **What it would need:** if this just means "let a user paste/display an Instagram post link,"
  that's a plain external link (see above). If it means embedding Instagram content or using
  their Graph API, that's a heavier, separate integration to scope later.

## Notifications

- **Today:** three Settings toggles exist (`wp-notif-prefs-v1`: `dailyReminder`,
  `taskReminders`, `eveningReminder`) but **there is no scheduling, permission request, or
  delivery code anywhere** — toggling them only saves the preference object. The Settings copy
  says so explicitly ("not active yet").
- **Capacitor path:** `@capacitor/local-notifications` (for reminders scheduled on-device) and/or
  `@capacitor/push-notifications` (for server-triggered ones, which would need Apple Push
  Notification service credentials and something server-side to send them — nothing like that
  exists today) — either is a genuinely new build, not a port, since there's no existing logic to
  carry over besides the three boolean preferences already sitting there waiting to be used.
- **Native path:** `UNUserNotificationCenter`, same story — new code, existing preference storage.

## Local storage

- **Today:** the app's entire offline/fast-path layer. Every `save()`/`load()` call writes to
  `localStorage` unconditionally, in addition to Supabase when signed in (see
  `docs/DATA_CONTRACTS.md`). Three additional flags bypass `save()`/`load()` and talk to
  `localStorage` directly (`wp-offline-mode-v1`, `wp-cloud-migrated-v1`,
  `wp-cloud-last-user-id-v1`) — all three are device-local by design and were never meant to
  sync.
- **Capacitor path:** the WebView's own `localStorage` behaves like a normal browser's — this
  layer needs no changes.
- **Native path:** `localStorage` doesn't exist; every one of the ~25 keys' worth of
  read/write logic needs a Swift equivalent (`UserDefaults` for small flags, `SwiftData` or a
  JSON-file cache for the larger per-day/per-photo objects) that preserves the exact same
  "local-first, sync-if-signed-in" behavior — this is the single largest piece of genuinely new
  code a native rewrite requires, precisely because it's currently so central to how the app
  works offline.

## Offline mode

- **Today:** "Continue offline" is a **distinct account mode**, not a network-status fallback —
  choosing it means never creating a Supabase session at all for that browser, ever, until the
  user explicitly logs in. There's no automatic "you're offline right now, working locally until
  reconnected" behavior for a *signed-in* user; if a signed-in user loses connectivity mid-session,
  writes still queue into `localStorage` (since `save()` always writes there first) but the
  Supabase upsert calls will simply fail silently in the background with no retry queue, no
  banner, no explicit recovery path visible in the code.
- **Implication for iOS:** this offline model can be carried over conceptually as-is (it doesn't
  depend on any browser API), but "silent failed writes with no retry" is worth deciding whether
  to keep or improve once building the native/Capacitor data layer — it's an existing gap, not
  something iOS introduces.

## Network handling

- **Today:** exactly one connectivity check in the entire app (`navigator.onLine`, used only to
  skip a pointless currency-rate fetch attempt while known-offline). No `online`/`offline` event
  listeners, no reactive re-sync when connectivity returns.
- **Capacitor path:** `navigator.onLine` still works inside the WebView (it's a standard Web API,
  not something Capacitor needs to shim), so this needs no change to keep working — though it's
  worth using `@capacitor/network` for a more reliable native-backed reachability check if this
  area gets built out further.
- **Native path:** `NWPathMonitor` is the direct replacement — new code, but a small, well-scoped
  piece.

## What to architecturally prepare in advance (regardless of path)

- A single, obvious place in the future codebase that reads `SUPABASE_URL`/`SUPABASE_ANON_KEY`
  from *config*, not hardcoded — so switching between DEV and PROD is a build setting, not a
  find-and-replace. (`index.html` itself does not need this change — it only ever points at PROD.)
- A small, explicit "sync status" concept (queued / syncing / synced / failed) if offline
  resilience is going to matter more once iOS exists — today's silent-failure behavior (above) is
  tolerable for a single browser tab but would be more noticeable across two platforms.
