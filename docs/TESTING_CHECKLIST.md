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
