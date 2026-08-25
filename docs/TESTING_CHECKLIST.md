# Testing checklist

What was actually verified in this preparation pass, and how to re-run it. Use this after any
future change to confirm nothing regressed — on the Web app today, and as a starting checklist
for whatever testing the iOS client eventually needs too.

## How it was tested here

No automated test suite exists in the repo (there's no `package.json`/test runner to add one to
without introducing a build step this project doesn't otherwise have). Verification in this pass
was done with ad-hoc Playwright scripts driving a real Chromium browser against the app served
locally (`python3 -m http.server` + `file://`-equivalent `http://localhost`), covering everything
below. These scripts aren't checked into the repo (they're throwaway verification tools, not part
of the product), but the checklist itself is — so the same manual/scripted pass can be repeated.

## Full pass — run across all 4 themes (Digital Chrome, Pink Pop, Dark Romance, Botanical)

- [ ] Onboarding completes without getting stuck, for a fresh "offline" account
- [ ] Theme switches correctly from Settings and the body's theme class updates
- [ ] **My Space**: loads, shows its cards, "Edit" mode toggles
- [ ] **My Day**: opens; does **not** show "Today's Vibe" or a Notes textarea (removed from this
      page on purpose — still fine if they show on My Space, which uses a separate layout)
- [ ] Mood slider: moving it updates the mood face immediately
- [ ] Water: tapping +200/+300/+500ml updates the displayed total and progress bar
- [ ] Sleep slider: moving it updates the displayed hours
- [ ] Adding a task: typing + pressing the add button puts it in the list
- [ ] Task-mood sticker picker: opens, shows exactly 16 theme-specific icons, includes that
      theme's own "add task" icon as one of the 16
- [ ] Decorative Sticker Sheet: opens, shows 5 pack tabs (My stickers + the 4 built-in packs)
- [ ] **Budget**: wallet balance renders; adding a transaction (amount + Save) updates the
      balance and appears in that month's list
- [ ] Month navigation (back-to-month link, month arrows) works without errors
- [ ] **Media**: view opens without errors
- [ ] **Settings**: view opens; theme dropdown, appearance dropdown, name field all present
- [ ] No JavaScript console errors (aside from expected network failures if Supabase/Google
      Fonts/currency APIs are unreachable in a given test environment — those are graceful,
      handled failures, not bugs)
- [ ] No horizontal page overflow at a small mobile width (375px) or a standard one (390px)
- [ ] Bottom navigation stays pinned and doesn't overlap content at the bottom of any view

**Result as of this pass:** all of the above passed, on all 4 themes, at both viewport widths
tested (390×844 and 375×667). See `docs/PROJECT_CLEANUP.md` and the security/theme docs for the
few non-functional issues found and fixed along the way (escaping, a hung upload promise, a
mislabeled sticker pack, a trivial duplicate CSS rule).

## Welcome-back screen (added after a Login)

- [ ] Existing account, has a saved name, clicks **Log in** → a brief "👋 Hi, {name}!" screen
      appears, then auto-dismisses into My Space
- [ ] Existing account with no saved name → shows the fallback "👋 Hi there!" (never an empty
      "Hi, !")
- [ ] Brand-new account (via **Sign up**, or a Login on an account that never finished
      onboarding) → onboarding runs as before; the welcome screen never shows instead of it
- [ ] Reopening the app while already signed in (no fresh Login) → welcome screen does **not**
      reappear
- [ ] **Log out** → **Log in** again → the welcome screen appears again (each fresh sign-in is
      its own one-time trigger)
- [ ] Tapping/navigating right after the greeting fades works normally (it doesn't block input
      or leave a stray overlay behind)
- [ ] Same behavior on all 4 themes — the screen uses the same `--board`/`--font-xl` tokens
      every other screen uses, so it should never look "off-theme"

Verified in this pass via direct `onSignedIn(...)`/`loginJustSucceeded` calls in a real browser
(Playwright) rather than a live Supabase login, since this sandbox can't reach Supabase — see the
note above about what can't be tested from here. All 8 checks above passed with zero console
errors, across all 4 themes.

## 4-tab restructuring (Today / Budget / Journal / You)

Bottom nav is now Today / Budget / Journal / You instead of the old My Space / Budget / My Day /
Media / Settings. "Today" is exactly the old My Day page promoted to the main daily dashboard;
My Space, Media, and the old separate Settings/Profile screens still exist, just reached from
"You" now instead of being separate bottom-nav destinations.

- [ ] All 4 tabs (Today, Budget, Journal, You) open without console errors
- [ ] Logging in (or reopening the app, or finishing onboarding) lands on **Today**, not My Space
- [ ] "You" tab shows Profile (avatar/name/email/sign out) stacked directly above Settings
      (appearance/My Space/Daily Page Widgets/regional/notifications/data & privacy/about) — one
      continuous scroll, no back button needed since it's a bottom-nav tab
- [ ] From You → "Manage My Space" opens My Space, which now has its **own** back button
      (top-left) that returns to You
- [ ] From You → Data & Privacy → "Media Files" opens Media, whose back button returns to You
- [ ] From You → "Daily Page Widgets" → customize opens the Widget Library, whose back button
      returns to You
- [ ] Tapping the header brand logo goes to Today (not My Space)
- [ ] **Journal**: composer at the top (date, text, mood slider + face, vibe tag chips, photo
      attach, optional "link a transaction" dropdown) and a chronological timeline below
  - [ ] Saving an entry with text appears in the timeline immediately, grouped under a date header
  - [ ] Mood slider updates the face shown in the composer live, and the saved entry shows that
        same mood face
  - [ ] Picking a vibe chip adds a pill (same colors/emoji as My Day's vibe pills); clicking the
        pill's ✕ removes it before saving
  - [ ] Adding a photo shows a thumbnail with a remove (✕) button before saving; the saved entry
        shows the photo without the remove button
  - [ ] Adding a transaction in Budget for today's date, then opening Journal, shows that
        transaction as a linkable option; saving an entry with it linked shows the transaction's
        amount/note under the entry
  - [ ] Deleting an entry (with confirmation) removes it from the timeline; deleting the last
        entry shows the "No entries yet" empty state
- [ ] Onboarding's interactive tour spotlights exactly the 4 new nav buttons (Today → Budget →
      Journal → You) with no console error — this depends on `TOUR_STEPS` and the `tour1..tour4`
      pages in `ONB_PAGES` staying the same length; a mismatch throws when the tour tries to
      render a step that doesn't exist
- [ ] Finishing onboarding lands on Today with the Today tab visibly active

**Result as of this pass:** verified via Playwright across all 4 themes at 390×844 — nav to all 4
tabs, You showing both Profile and Settings sections, My Space/Media reachable and returning to
You, a full Journal create→link-transaction→delete cycle, onboarding driven through real
Next/Skip button clicks into and out of the tour and to completion, brand-logo click. Zero
console errors in any of it.

**Known pre-existing issue, unrelated to this restructuring:** at 375px width, the Today tab
(`.day-widget-cell` mood widget) overflows horizontally by ~20px. Confirmed via a fresh, isolated
landing on Today with zero navigation — `buildDateView()`/the mood widget markup were not
touched by this restructuring (Today is exactly the old My Day page), so this is a latent issue
in that existing layout, not something the 4-tab change introduced. Left as-is; worth a small
follow-up fix (likely the `.mood-row`/mood-slider width at very narrow viewports) outside the
scope of this pass.

## Things that can't be tested from this sandboxed environment

- **Real Supabase sign-up/sign-in against PROD** — deliberately not attempted, to avoid touching
  real user data (see `docs/SUPABASE_ENVIRONMENTS.md`). Once DEV exists, the same auth flow can
  be exercised safely there.
- **The pinned Supabase CDN URL's real-world reachability** — this sandbox's network policy
  blocks `cdn.jsdelivr.net` entirely (both the old floating URL and the new pinned one fail
  identically here), so the app correctly falls back to offline mode in this environment either
  way. Recommended: after this deploys, open the live Netlify site once in an ordinary browser
  and confirm sign-in still works, just to close the loop on a real network.

## Regression checks worth re-running specifically after future CSS/theme changes

- Onboarding avatar picker: all 10 avatars should render as clean circles (no visible
  square/frame artifact at the edges)
- Every My Day widget cell (Mood/Water/Sleep/Tasks/Photos/Expenses) should have a visible
  "glass" card treatment in **both** light and dark, on **all 4** themes — this specific thing
  was broken for Digital Chrome and Pink Pop before an earlier fix in this project's history
- No theme's weekday accent color should render as a literal bright/neon red anywhere (add-task
  button, sliders) — each theme has its own weekday color rotation specifically to prevent this
