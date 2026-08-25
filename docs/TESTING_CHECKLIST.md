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

## UX/technical fixes pass (avatar, transactions, theme-switch bug, contrast, onboarding)

A follow-up pass fixing several concrete bugs and UX issues, without touching any theme's
visual design/palette concept:

- [ ] **Avatar**: the avatar shown at the top of My Profile is a clean circle in every theme —
      no square corners, no white halo/gap at the edges. It uses the same
      oversize-image-inside-a-clipping-circle technique as the avatar picker grid below it
      (`.profile-avatar-hero-clip`), not a bare `<img>` with its own border-radius.
- [ ] **Add Transaction**: Budget's main screen shows a single "+ Add transaction" button, not
      an always-open form. Tapping it opens a bottom sheet (same component the Widget Library
      already uses) with Expense/Income toggle → amount/currency/date/category-or-source/note →
      Save. Saving closes the sheet and the transaction appears in the list — existing
      add/edit/delete/currency-management functionality all still works, just relocated.
- [ ] **Budget spending ring**: a donut ring sits above the Income/Spent/Net stats, its center
      showing net (income − spent). The ring fills red instead of the theme accent when spending
      exceeds income for the month. Built from existing theme tokens (`--accent`/`--danger`/
      `--paper`/`--paper2`) via `conic-gradient` — check it renders correctly (no visual
      leftovers, correct color) in all 4 themes.
- [ ] **Today's Vibe is gone everywhere**: no vibe/tag picker on My Day, My Space, the Widget
      Library catalog, onboarding's widget picker, or on a Journal entry. The `VIBES`/
      `customVibes` system, `wp-vibes-custom-v1`, and every `vibe*` widget/UI/string were removed
      (the *task*-mood sticker feature — `todo.vibe`, the small mood emoji on a task — is a
      separate, unrelated feature and is unaffected).
- [ ] **Theme switching leaves no stale colors**: sign out, change theme on one account/device,
      then sign back in on a browser whose local `wp-theme-v5` still says the OLD theme — the
      app must fully switch to the account's actual theme, including JS-driven per-theme colors
      (a day's own accent color, mood face, task-mood icons), not just the CSS body class. This
      was a real bug (`onSignedIn` reapplied the theme's CSS class from the cloud value but never
      updated the `currentTheme` JS variable those lookups read), now fixed. Also re-verify plain
      in-app theme switching (Settings dropdown, Year view swatches) still works normally in all
      4 themes, switched back and forth several times in a row.
- [ ] **Digital Chrome accent**: the primary accent/link/button color is a deeper navy-indigo
      (light) / soft lavender-blue (dark) — not the old bright sky-blue. Nothing else in the
      palette (backgrounds, decorative gradients, the weekday color rotation) changed.
- [ ] **Dark Romance (light) contrast**: header wordmark, back-links, and the sync badge stay
      readable over every part of the per-screen photo background (not just its darker areas).
      Textarea/input placeholders (e.g. Journal's "What happened today?") are clearly visible,
      not washed out — check this in all 4 themes, since the placeholder-contrast fix is global.
- [ ] **Dark Romance font**: headings and diary-style text use Fraunces (same face Botanical and
      Digital Chrome already use) instead of the old Cormorant Garamond, in both light and dark.
- [ ] **Onboarding composition**: "Hi." / "Let's get to know each other." / the name field (and
      the other short text-only onboarding pages — Why, Appearance, Avatar, Done) read as
      vertically centered within the diary page, not pinned to the top with empty space below.
      Longer pages (widget picker, first-day) are unaffected.
- [ ] **Onboarding name field**: the placeholder reads "Your name", never the literal text "Eve".
- [ ] **Onboarding page-turn speed**: turning a page is a bit slower and smoother than before
      (~0.62s vs. the old ~0.46s) — noticeably calmer without feeling sluggish. The
      prefers-reduced-motion fallback (instant opacity cross-fade) is untouched.

**Result as of this pass:** verified via Playwright across all 4 themes — avatar circular clip,
Today's Vibe absent from every screen checked (Today, Journal, Widget Library), the transaction
button/sheet/save flow, the spending ring's color and computed `--accent` per theme, Dark
Romance's forest-light `--ink-dim`/font/header-shadow computed values, and onboarding's
placeholder/centering/transition-duration computed values — all correct, zero console errors.

## Full pass — run across all 4 themes (Digital Chrome, Pink Pop, Dark Romance, Botanical)

- [ ] Onboarding completes without getting stuck, for a fresh "offline" account
- [ ] Theme switches correctly from Settings and the body's theme class updates
- [ ] **My Space**: loads, shows its cards, "Edit" mode toggles
- [ ] **My Day**: opens; does **not** show a Notes textarea (removed from this page on purpose —
      still fine if it shows on My Space, which uses a separate layout)
- [ ] "Today's Vibe" does not appear anywhere in the app — not as a My Day/My Space widget, not
      in the widget customize screen's catalog, not in onboarding's widget picker, and not as a
      tag picker on a Journal entry (the feature was removed entirely, not just hidden)
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

## 5-tab restructuring (Budget / Journal / Today / Media / Settings)

Bottom nav is now Budget / Journal / Today / Media / Settings, in that left-to-right order,
instead of the old My Space / Budget / My Day / Media / Settings. "Today" is exactly the old My
Day page, promoted to the main daily dashboard and the app's home (replacing My Space in that
role). Media and Settings are real bottom-nav tabs again (an intermediate pass had briefly
folded them under a "You" tab together with Profile — that was reverted per follow-up feedback).
My Profile (avatar, name, email, password, sign out) is its own screen again, reached via the
header avatar button, separate from Settings — also as before. My Space is still not a bottom-nav
tab; it's reached from Settings ("Manage My Space").

- [ ] All 5 tabs (Budget, Journal, Today, Media, Settings) open without console errors, in that
      left-to-right order
- [ ] Logging in (or reopening the app, or finishing onboarding) lands on **Today**, not My Space
- [ ] Tapping the header avatar opens **My Profile** (avatar picker, name, email, change
      email/password when signed in, sign out) — a separate screen from Settings, with its own
      back button that returns to Today
- [ ] **Settings** tab shows appearance/My Space/Daily Page Widgets/regional/notifications/
      data & privacy (incl. Media Files link)/about — its own back button also returns to Today
- [ ] From Settings → "Manage My Space" opens My Space, whose back button returns to **Settings**
      (not Today)
- [ ] From Settings → "Daily Page Widgets" → customize opens the Widget Library, whose back
      button also returns to Settings
- [ ] **Media** tab opens the year/month photo browser directly; its own back button returns to
      Today (same as before this whole restructuring)
- [ ] Tapping the header brand logo goes to Today (not My Space)
- [ ] **Journal**: composer at the top (date, text, mood slider + face, photo attach, optional
      "link a transaction" dropdown) and a chronological timeline below — no tag/vibe picker
  - [ ] Saving an entry with text appears in the timeline immediately, grouped under a date header
  - [ ] Mood slider updates the face shown in the composer live, and the saved entry shows that
        same mood face
  - [ ] Adding a photo shows a thumbnail with a remove (✕) button before saving; the saved entry
        shows the photo without the remove button
  - [ ] Adding a transaction in Budget for today's date, then opening Journal, shows that
        transaction as a linkable option; saving an entry with it linked shows the transaction's
        amount/note under the entry
  - [ ] Deleting an entry (with confirmation) removes it from the timeline; deleting the last
        entry shows the "No entries yet" empty state
- [ ] Onboarding's interactive tour spotlights exactly the 5 real nav buttons, in order Budget →
      Journal → Today → Media → Settings, with no console error — this depends on `TOUR_STEPS`
      and the `tour1..tour5` pages in `ONB_PAGES` staying the same length; a mismatch throws when
      the tour tries to render a step that doesn't exist
- [ ] Finishing onboarding lands on Today with the Today tab visibly active

**Result as of this pass:** verified via Playwright — nav to all 5 tabs in the correct order,
Media/Settings working as standalone tabs, the avatar opening a separate My Profile screen
distinct from Settings, Profile/Settings back buttons returning to Today, My Space reachable from
Settings and returning to Settings, a full Journal create→link-transaction→delete cycle (from the
earlier pass, unaffected by this nav-order follow-up), and onboarding driven through the real
Next/Skip UI into and out of the tour to completion landing on Today. Zero console errors
throughout.

**Known pre-existing issue, unrelated to this restructuring:** at 375px width, the Today tab
(`.day-widget-cell` mood widget) overflows horizontally by ~20px. Confirmed via a fresh, isolated
landing on Today with zero navigation — `buildDateView()`/the mood widget markup were not
touched by this restructuring (Today is exactly the old My Day page), so this is a latent issue
in that existing layout, not something the 4-tab change introduced. Left as-is; worth a small
follow-up fix (likely the `.mood-row`/mood-slider width at very narrow viewports) outside the
scope of this pass.

## Journal redesign — "keep what you found today" (replaces the composer+timeline Journal)

Journal changed from a freeform mood/text diary timeline to a Today-first board of typed
"moments" (Photo/Place/Song/Movie/Recipe/Link/Note), private by default with an optional public
Explore feed. See `docs/DATA_CONTRACTS.md` → `wp-journal-moments-v1` and
`docs/JOURNAL_PUBLIC_TABLE.md` for the data model and the required Supabase table. No visual
theme/palette/typography/nav-architecture changes were made — the new screens inherit whichever
theme is active, exactly like Budget/Media already do.

- [ ] Opening Journal from the bottom nav always lands on **today**, with today's real weekday
      and date shown (e.g. "Tuesday, August 25"), regardless of what date was viewed last time
- [ ] Empty state on a fresh account: "Did you find something worth keeping today?" +
      "+ Keep a Moment", no console errors
- [ ] **Keep a Moment** opens a sheet with exactly 7 options: Photo, Place, Song, Movie, Recipe,
      Link, Note
- [ ] **Photo**: pick an image → preview appears in the form; title/description optional; saves
      without a title; the moment's card shows a real thumbnail (not the generic icon)
- [ ] **Place**: name required (Save does nothing without it), map URL + description optional;
      an entered map URL renders as a working "Open map" link in the moment's detail view
- [ ] **Song**: name required, artist/link/description optional; an entered link opens in a new
      tab from the detail view
- [ ] **Movie**: title required, link/photo/description optional
- [ ] **Recipe**: name required, link/photo/description optional; the link stays clickable
- [ ] **Link**: URL required (Save does nothing without it), title optional; the URL opens in a
      new tab
- [ ] **Note**: note text required, title optional
- [ ] After saving any type, the sheet closes and the new moment appears in today's list with
      the right type icon/label
- [ ] Tapping a saved moment opens its detail (title/description/image/link as applicable),
      with **Edit** and **Delete** actions
- [ ] Editing a moment prefills every existing field correctly and updates the card in place
- [ ] Deleting a moment asks for confirmation, then removes it from the list
- [ ] A Photo moment's full image is not requested until you actually open that moment (Network
      tab / DOM: the list only ever renders `thumb`, the detail view is what sets `image`)
- [ ] Tapping the calendar icon lets you pick a previous date; that date's moments load (or
      "Nothing saved on this day." + "+ Keep a Moment" if none)
- [ ] Creating a moment while viewing a previous date saves it under that date, not today
- [ ] Leaving Journal (any other tab) and coming back always resets to today, even if a previous
      date or Explore was open when you left
- [ ] A new moment is **private** by default (🔒 badge, no explicit action needed to keep it that
      way)
- [ ] **Make Public** on a moment's detail flips the badge to 🌍 and the button to
      **Make Private**; toggling back removes it from Explore immediately (requires the
      `public_journal_moments` table from `docs/JOURNAL_PUBLIC_TABLE.md` to actually reach
      Explore — without it, the toggle still flips locally and just logs a console warning)
- [ ] **Explore** (button next to the calendar icon, inside Journal — confirm it did **not** add
      a 6th bottom-nav tab; nav stays Budget/Journal/Today/Media/Settings) shows public moments
      from other accounts, or a clear empty/unavailable message when signed out or offline
- [ ] Opening a public moment from Explore shows its content and a **Save to My Journal** button
- [ ] Saving an Explore moment adds it to today's Journal, privately, with "Saved from SVOJ
      Explore · by {author}" shown in its detail — and does **not** alter or unpublish the
      original public moment
- [ ] A user can only ever edit/delete their **own** private moments (no UI path to another
      account's private data — this was never exposed anywhere, same as every other per-user key)
- [ ] All of the above persists correctly after a full page reload
- [ ] Mobile viewport (390×844 and narrower) — no horizontal overflow anywhere in Journal,
      Keep-a-Moment sheet, or Explore grid
- [ ] All 4 themes (Digital Chrome, Pink Pop, Dark Romance, Botanical), both light and dark: the
      Journal screens read as that theme (correct paper/ink/accent colors, no leftover styling
      from another theme), with zero new theme-specific CSS added to make this true
- [ ] Everything outside Journal (Budget, Today, Media, Settings, onboarding, avatar system,
      theme switching) still works exactly as before this change

## Things that can't be tested from this sandboxed environment

- **Real Supabase sign-up/sign-in against PROD** — deliberately not attempted, to avoid touching
  real user data (see `docs/SUPABASE_ENVIRONMENTS.md`). Once DEV exists, the same auth flow can
  be exercised safely there.
- **The pinned Supabase CDN URL's real-world reachability** — this sandbox's network policy
  blocks `cdn.jsdelivr.net` entirely (both the old floating URL and the new pinned one fail
  identically here), so the app correctly falls back to offline mode in this environment either
  way. Recommended: after this deploys, open the live Netlify site once in an ordinary browser
  and confirm sign-in still works, just to close the loop on a real network.
- **Journal Explore against a real second account** — this sandbox can't reach the real
  Supabase project (see above) or run the `public_journal_moments` SQL migration itself (see
  `docs/JOURNAL_PUBLIC_TABLE.md`), so the actual cross-account path ("make public → a *different*
  signed-in account sees it in Explore → that account saves it to their own Journal") could only
  be exercised here by stubbing `journalFetchExplore()`'s return value and rendering the Explore
  grid/detail/"Save to My Journal" from that fixture — real end-to-end network calls to
  `public_journal_moments` were never made. What *was* verified for real: Make Public/Make
  Private call Supabase and fail silently with a console warning (expected, since the table
  doesn't exist yet in this sandbox's project), and every private-Journal path is fully
  unaffected either way. Recommended: once that table is created, repeat this with two real
  accounts on the deployed site before considering Explore done.

## Regression checks worth re-running specifically after future CSS/theme changes

- Onboarding avatar picker: all 10 avatars should render as clean circles (no visible
  square/frame artifact at the edges)
- Every My Day widget cell (Mood/Water/Sleep/Tasks/Photos/Expenses) should have a visible
  "glass" card treatment in **both** light and dark, on **all 4** themes — this specific thing
  was broken for Digital Chrome and Pink Pop before an earlier fix in this project's history
- No theme's weekday accent color should render as a literal bright/neon red anywhere (add-task
  button, sliders) — each theme has its own weekday color rotation specifically to prevent this
