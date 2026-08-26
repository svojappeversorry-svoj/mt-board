#!/usr/bin/env python3
"""
Generates docs/sql/editorial_seed.sql — the one-time (but safely re-runnable) SQL migration
that seeds the official @svoj editorial account's public Journal moments.

Why this is a generator rather than a hand-written SQL file: ~130 rows of natural-language
title/description text contain apostrophes, quotes and other characters that are easy to get
wrong by hand inside SQL string literals. Generating the file programmatically guarantees every
value is escaped correctly and every id is unique, and it also validates the dataset (see
`validate()`) before ever writing SQL — the only real verification available in an environment
that cannot connect to a live Supabase project to test the migration end-to-end.

Run: python3 scripts/generate_editorial_seed_sql.py
Output: docs/sql/editorial_seed.sql (overwritten every run — this script is the source of truth,
the generated .sql file is a build artifact, both are committed so the SQL can be reviewed/run
without needing Python at read time).

Content design notes (see docs/EDITORIAL_SEED.md for the full picture):
- No 'photo'-type moments. Sourcing ~20+ distinct, appropriately-licensed real photographs for
  unrelated recipe/place/fashion/interior subjects isn't achievable from this environment without
  either downloading copyrighted images (explicitly disallowed) or reusing the app's own avatar
  art (thematically wrong — cartoon animal characters do not belong on a recipe or café entry).
  The task's own instructions allow this: "If a valid external URL/image cannot be used for a
  particular type, choose another suitable piece of content instead." Every entry below instead
  uses one of the other 6 types, all of which render a clean type-icon fallback when there's no
  thumbnail — an existing, first-class UI state, not a degraded one.
- Every external_url is either (a) a *search* URL on a real, major, stable site (guaranteed to
  resolve to a real working page regardless of the exact query, since the domain and route are
  real), (b) a real homepage of a well-known site, or (c) a specific Wikipedia article only for
  well-known, unambiguous topics. None of these were fabricated or guessed as a specific deep
  link (e.g. no invented blog post slug, no guessed video/track id) — see the task's explicit
  "do not invent fake URLs that lead nowhere."
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

# The real email behind the @svoj Supabase Auth account — change this and re-run the generator
# if the account is ever recreated under a different address. Only referenced here so it never
# drifts out of sync between the generated SQL and docs/EDITORIAL_SEED.md.
SVOJ_EMAIL = 'svojappeversorry@gmail.com'

OUT_PATH = "docs/sql/editorial_seed.sql"

def qs(query):
    return quote(query, safe="")

def allrecipes(q): return f"https://www.allrecipes.com/search?q={qs(q)}"
def seriouseats(q): return f"https://www.seriouseats.com/search?q={qs(q)}"
def bonappetit(q): return f"https://www.bonappetit.com/search/{qs(q)}"
def simplyrecipes(q): return f"https://www.simplyrecipes.com/?s={qs(q)}"
def nyt_cooking(q): return f"https://cooking.nytimes.com/search?q={qs(q)}"
def epicurious(q): return f"https://www.epicurious.com/search/{qs(q)}"
def gmaps(q): return f"https://www.google.com/maps/search/{qs(q)}"
def lonelyplanet(q): return f"https://www.lonelyplanet.com/search?q={qs(q)}"
def atlasobscura(q): return f"https://www.atlasobscura.com/search?q={qs(q)}"
def tripadvisor(q): return f"https://www.tripadvisor.com/Search?q={qs(q)}"
def spotify(q): return f"https://open.spotify.com/search/{qs(q)}"
def ytmusic(q): return f"https://music.youtube.com/search?q={qs(q)}"
def imdb(q): return f"https://www.imdb.com/find/?q={qs(q)}"
def letterboxd(q): return f"https://letterboxd.com/search/{qs(q)}/"
def wiki(title): return f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"

RECIPE = [
    ("Creamy Garlic Chicken for a Weeknight Win",
     "One pan, one sauce, and it somehow still tastes like more effort than it was.",
     allrecipes("creamy garlic chicken")),
    ("The One-Pan Lemon Chicken That Never Fails",
     "Bright, simple, and forgiving enough for a Tuesday when nothing else sounds good.",
     seriouseats("lemon chicken")),
    ("Crispy Chicken Thighs, No Fuss Required",
     "Skin-on thighs and a hot pan — the kind of dinner that doesn't need a recipe card memorized.",
     simplyrecipes("crispy chicken thighs")),
    ("Honey Garlic Chicken in Under 30 Minutes",
     "Sticky, sweet, a little sharp — good over rice, better with leftovers the next day.",
     allrecipes("honey garlic chicken")),
    ("Sheet Pan Chicken for Nights You Don't Want Dishes",
     "Everything roasts together, and cleanup is one tray. That's the whole pitch.",
     nyt_cooking("sheet pan chicken")),
    ("The Pasta Sauce Worth Learning by Heart",
     "No recipe needed after the third time — just tomatoes, garlic, and patience.",
     seriouseats("simple tomato pasta sauce")),
    ("A Creamy Pasta That Doesn't Need Cream",
     "Cheese, pasta water, and a bit of technique do all the work here.",
     bonappetit("cacio e pepe")),
    ("Weeknight Pasta With Whatever's in the Fridge",
     "A loose formula more than a recipe — the kind of dinner that adapts to a half-empty crisper.",
     simplyrecipes("pantry pasta")),
    ("The Lemon Pasta I Keep Coming Back To",
     "Light enough for summer, still satisfying enough to actually count as dinner.",
     allrecipes("lemon pasta")),
    ("A Chocolate Dessert That Actually Feels Fancy",
     "Looks like it took hours. Doesn't. Worth keeping in the back pocket for guests.",
     epicurious("chocolate lava cake")),
    ("The Simplest Fruit Dessert for Summer",
     "Whatever's ripe, a little sugar, and the oven does the rest.",
     simplyrecipes("fruit crumble")),
    ("A No-Bake Dessert for Lazy Sundays",
     "No oven, minimal cleanup, and somehow still feels like a real dessert.",
     allrecipes("no bake dessert")),
    ("The Cookie Recipe I Trust Every Time",
     "Consistent, crowd-pleasing, and forgiving if you forget to chill the dough.",
     bonappetit("chocolate chip cookies")),
    ("A Breakfast Bowl Worth Waking Up For",
     "Grains, something crisp, something soft — a template rather than a strict recipe.",
     nyt_cooking("savory breakfast bowl")),
    ("Overnight Oats That Don't Taste Like a Compromise",
     "Made the night before, and somehow the only breakfast that actually happens on weekdays.",
     simplyrecipes("overnight oats")),
    ("The Weekend Pancakes Worth the Extra Step",
     "Resting the batter actually makes a difference — worth it when there's time to spare.",
     allrecipes("fluffy pancakes")),
    ("A Savory Breakfast for People Who Skip Sweet",
     "Eggs, something salty, something green — proof breakfast doesn't need to be sugar.",
     seriouseats("savory breakfast")),
    ("A Healthy Meal That Doesn't Feel Like One",
     "Built around what's actually good, not what's technically allowed.",
     bonappetit("healthy dinner bowl")),
    ("The Salad I Actually Crave",
     "Grains and something roasted turn a salad into an actual meal, not a side thought.",
     simplyrecipes("grain salad")),
    ("A Protein-Packed Lunch That Reheats Well",
     "Made once, eaten four times — the whole point of meal prep, finally working.",
     allrecipes("meal prep chicken bowl")),
    ("Dinner for Nights You Don't Want to Think",
     "One tray, one decision, done — sheet pan dinners exist for exactly this mood.",
     seriouseats("sheet pan dinner")),
    ("A Dinner That Looks Like More Effort Than It Was",
     "One pot, minimal chopping, and it still plates like it took real planning.",
     nyt_cooking("one pot dinner")),
    ("The Soup That Fixes Most Evenings",
     "Simmers while everything else in the day settles down. Freezes well too.",
     epicurious("comforting soup")),
]

PLACE = [
    ("A Café Worth Rearranging Your Day For",
     "The kind of place where 'just one coffee' quietly turns into two hours.",
     gmaps("best specialty coffee shop")),
    ("The Kind of Café You Stay in Too Long",
     "Good light, better chairs, and no one rushing you toward the door.",
     gmaps("cozy café with books")),
    ("Coffee Worth a Detour",
     "Not on the way to anything — which is exactly why it's worth the trip.",
     gmaps("third wave coffee roastery")),
    ("A Neighborhood Café That Feels Like a Secret",
     "No sign out front worth noticing, and somehow that's part of the appeal.",
     gmaps("hidden neighborhood café")),
    ("A Restaurant That Earns Every Bit of Its Reputation",
     "Booked out for a reason — worth planning the trip around, not the other way around.",
     gmaps("must try local restaurant")),
    ("Dinner Somewhere That Feels Like an Occasion",
     "The kind of place worth the good outfit, even on a random Tuesday.",
     gmaps("romantic dinner restaurant")),
    ("The Kind of Restaurant Locals Actually Recommend",
     "Not the one every guidebook mentions — the one people who live there actually go back to.",
     gmaps("local favorite restaurant")),
    ("A Small Restaurant Worth Booking Ahead For",
     "Ten tables, one menu, no shortcuts — reservations for a reason.",
     gmaps("small plates restaurant")),
    ("A View Worth Getting Up Early For",
     "Loses something after 8am — this is a set-an-alarm kind of spot.",
     gmaps("best sunrise viewpoint")),
    ("The Kind of Place That Looks Unreal in Photos",
     "And somehow still undersells it in person.",
     gmaps("scenic viewpoint")),
    ("A Quiet Spot That Feels Far From Everything",
     "Twenty minutes from the center of things, and it feels like a different country.",
     gmaps("quiet nature spot")),
    ("Somewhere Worth Watching the Sunset From",
     "Bring something to sit on and no real plan for after.",
     gmaps("best sunset spot")),
    ("A Travel Spot That's Worth the Long Flight",
     "Not the easiest place to get to. Also not comparable to anywhere closer.",
     lonelyplanet("underrated travel destination")),
    ("The Kind of Town You Wish You'd Booked Longer For",
     "Two nights felt like a rough draft — this one deserves the full week.",
     lonelyplanet("charming small town")),
    ("A Coastal Town Worth the Detour",
     "Smaller than it looks on the map, and better for exactly that reason.",
     atlasobscura("coastal town")),
    ("An Island Worth Slowing Down For",
     "Nothing urgent happens here, which is the entire point of going.",
     lonelyplanet("quiet island getaway")),
    ("A City Break That Doesn't Feel Rushed",
     "Small enough to actually see, slow enough to actually enjoy.",
     lonelyplanet("weekend city break")),
    ("The Market That's Worth Getting Lost In",
     "No map necessary — half the appeal is not knowing what's around the next stall.",
     gmaps("local market")),
    ("A Bookstore Worth an Afternoon",
     "The kind of shop where 'just browsing' rarely holds up.",
     gmaps("independent bookstore")),
    ("The Park Everyone Forgets Is There",
     "Two streets off the main road, and somehow always quiet.",
     gmaps("hidden city park")),
    ("A Bakery That's Worth the Early Alarm",
     "Sells out by 10am most days — worth being one of the first through the door.",
     gmaps("best local bakery")),
    ("The Street Everyone Photographs for a Reason",
     "Overexposed on every feed, and still worth seeing for yourself.",
     gmaps("picturesque old street")),
    ("A Rooftop Worth Knowing About Before Sunset",
     "Arrive early enough to get a seat — this one fills up fast for a reason.",
     gmaps("rooftop bar view")),
]

SONG = [
    ("The Song That Actually Feels Like Summer",
     "Not because of the lyrics — just the way the whole thing opens up around the chorus.",
     spotify("summer feel good song")),
    ("A Song for Driving With the Windows Down",
     "Better at a slightly-too-loud volume, ideally with nowhere urgent to be.",
     spotify("road trip summer song")),
    ("The Track That Belongs on Every Beach Day",
     "Warm, unbothered, and somehow makes sunscreen smell better in memory.",
     spotify("beach day playlist")),
    ("A Song That Sounds Like the Last Warm Evening",
     "The one that plays right before summer quietly turns into September.",
     spotify("end of summer song")),
    ("The Song for 2am Thoughts",
     "Not sad exactly — just honest in a way that only makes sense that late.",
     spotify("late night thinking song")),
    ("A Track That Sounds Like an Empty Street",
     "Made for walking somewhere with no particular destination.",
     spotify("late night city song")),
    ("The Song Made for Driving Home Alone",
     "Better than any conversation you'd have had at that hour anyway.",
     spotify("late night drive song")),
    ("A Slow Song for When the Day Finally Ends",
     "The kind of track that gives permission to stop doing things.",
     spotify("wind down song")),
    ("The Song That Actually Sounds Like Falling for Someone",
     "Not the loud, obvious kind — the quieter, slightly nervous kind.",
     spotify("romantic love song")),
    ("A Slow Dance Song Worth Learning the Words To",
     "Old enough that everyone already half-knows it, which is exactly the appeal.",
     spotify("slow dance song")),
    ("The Song for a First Date Playlist",
     "Not too on the nose, not too random — the hardest kind to pick.",
     spotify("first date song")),
    ("A Love Song That Isn't Overplayed",
     "Somehow missed the algorithm entirely, which makes it feel more like a discovery.",
     spotify("underrated love song")),
    ("The Song That Makes Getting Ready Feel Like an Event",
     "Turns a plain mirror and bad lighting into something that feels like a montage.",
     spotify("getting ready playlist")),
    ("A Track for Doing Your Makeup Too Slowly",
     "Ten minutes of routine somehow stretched into twenty, and it's this song's fault.",
     spotify("confidence song")),
    ("The Song That Belongs Before Any Night Out",
     "The first track, always — sets the tone for everything after it.",
     spotify("pre night out song")),
    ("A Song With Main Character Energy",
     "Walk-down-the-street-like-it's-a-movie energy. No further explanation needed.",
     spotify("main character playlist")),
    ("The Playlist for Doing Absolutely Nothing",
     "Background music for a day with no real plans, which is its own kind of luxury.",
     spotify("chill lo-fi playlist")),
    ("A Quiet Soundtrack for Working Slowly",
     "Unobtrusive enough to disappear into the background within a minute.",
     spotify("focus chill playlist")),
    ("The Kind of Music That Fixes a Bad Mood",
     "Not upbeat exactly — just steady enough to make everything else feel more manageable.",
     spotify("mood lifting chill music")),
    ("A Playlist for Rainy Afternoons",
     "Best with a window seat and absolutely no obligation to go outside.",
     spotify("rainy day playlist")),
    ("The Song for Watching the World Slow Down",
     "Long, patient, and in no hurry to get anywhere — exactly like the best afternoons.",
     spotify("calm acoustic song")),
    ("A Track That Sounds Like a Sunday",
     "Unhurried in a way weekdays never quite manage.",
     spotify("sunday morning song")),
]

MOVIE = [
    ("The Fashion Movie Everyone Should See at Least Once",
     "Less about the clothes than about who gets to decide what's cool — still holds up completely.",
     imdb("The Devil Wears Prada")),
    ("A Film That's Basically a Style Reference",
     "Every frame looks considered — worth watching once just for the tailoring.",
     imdb("Phantom Thread")),
    ("The Movie That Made an Entire Generation Want Bangs",
     "Whimsical without ever tipping into precious — and the styling is doing real work.",
     imdb("Amelie")),
    ("A Film Worth Watching Just for the Wardrobe",
     "The plot is fine. The costumes are the real main character.",
     imdb("Marie Antoinette 2006")),
    ("The Movie for When You Need Everything to Be Okay",
     "Warm, unhurried, and mostly about food — the emotional equivalent of a good meal.",
     imdb("Chef 2014")),
    ("A Film That Feels Like a Warm Blanket",
     "Kind in a way that doesn't feel naive — rare, and worth protecting.",
     imdb("Paddington 2014")),
    ("The Comfort Movie That Never Gets Old",
     "Familiar enough to half-watch, good enough to fully watch anyway.",
     imdb("Julie and Julia")),
    ("A Slow, Kind Film for a Hard Week",
     "Quiet, a little sentimental, and exactly what a rough few days actually needs.",
     imdb("About Time 2013")),
    ("The Romantic Movie That Actually Holds Up",
     "Rewatched more than any other film on this list, for good reason.",
     imdb("Pride and Prejudice 2005")),
    ("A Love Story Worth Rewatching Every Year",
     "The kind of film that gets a little better with each rewatch, not worse.",
     imdb("Notting Hill")),
    ("The Film That Makes You Believe in Timing",
     "Mostly two people talking, and somehow more romantic than almost anything louder.",
     imdb("Before Sunrise")),
    ("A Quiet Romance Worth Sitting With",
     "Restrained in a way that makes the small moments hit harder.",
     imdb("In the Mood for Love")),
    ("The Thriller That Actually Earns Its Twist",
     "The kind of ending that changes how the first hour reads in hindsight.",
     imdb("Gone Girl")),
    ("A Film That Keeps You Guessing Until the End",
     "Rewatchable purely to catch what you missed the first time.",
     imdb("Knives Out")),
    ("The Thriller Worth Watching With the Lights Off",
     "Slow-building tension that earns every uncomfortable minute.",
     imdb("Prisoners 2013")),
    ("A Slow-Burn Thriller Worth the Patience",
     "Long, meticulous, and never in a rush to give you an answer.",
     imdb("Zodiac 2007")),
    ("The Movie Worth Watching Every Single Year",
     "Some films age. This one just gets more comfortable.",
     imdb("Little Women 2019")),
    ("A Film That Gets Better Every Time",
     "Dense enough that a rewatch always turns up something missed before.",
     imdb("The Grand Budapest Hotel")),
    ("The Movie That's Basically a Reset Button",
     "Strange, beautiful, and somehow calming despite not being calm at all.",
     imdb("Spirited Away")),
    ("A Film Worth Revisiting on a Rainy Day",
     "Funny and a little sad in exactly the right proportions.",
     imdb("Little Miss Sunshine")),
    ("The Movie That Never Feels Like a Rewatch",
     "The kind of film that still finds new things to say the fourth time through.",
     imdb("La La Land")),
    ("A Film Worth Watching Again Just for the Score",
     "Watch it for the story once, then again purely for the soundtrack.",
     imdb("Interstellar")),
]

LINK = [
    ("A Site Worth Bookmarking for Actually Useful Reviews",
     "Recommendations that assume you'll actually use the thing, not just admire it.",
     "https://www.nytimes.com/wirecutter"),
    ("The Reading List Site That's Worth the Habit",
     "Half social network, half spreadsheet for anyone who reads more than they finish.",
     "https://www.goodreads.com"),
    ("A Search Engine for Ideas, Not Just Products",
     "Better for 'what could this room look like' than any actual furniture site.",
     "https://www.pinterest.com"),
    ("A Long-Read Worth the Twenty Minutes",
     "The kind of writing that's worth closing every other tab for first.",
     "https://www.nytimes.com"),
    ("An Archive Worth Getting Lost In",
     "Thoughtful, slow, and the opposite of anything designed to be scrolled quickly.",
     "https://www.themarginalian.org"),
    ("The Kind of Writing That Actually Stays With You",
     "Long-form, patient, and rarely written to be forgotten by tomorrow.",
     "https://www.theatlantic.com"),
    ("A Publication Worth Following for the Ideas Alone",
     "Good even when the specific topic isn't your thing.",
     "https://www.newyorker.com"),
    ("The Recipe Site I Trust More Than My Own Notes",
     "Tested enough times that the comments section rarely disagrees.",
     "https://www.seriouseats.com"),
    ("A Site That Makes Cooking Feel Less Like a Chore",
     "Short ingredient lists, clear steps, minimal fuss.",
     "https://www.simplyrecipes.com"),
    ("The Recipe Archive Worth Bookmarking",
     "Deep enough to have a version of almost anything you're craving.",
     "https://cooking.nytimes.com"),
    ("A Cooking Site With Genuinely Reliable Recipes",
     "Rarely a surprise in a bad way — which is all you really want from a recipe.",
     "https://www.bonappetit.com"),
    ("The Fashion Site Worth Checking Every Season",
     "More archive than trend report, which makes it age well.",
     "https://www.vogue.com"),
    ("A Style Archive Worth Scrolling Through Slowly",
     "Good for borrowing ideas rather than copying outfits outright.",
     "https://www.elle.com"),
    ("The Site for Outfit Ideas That Don't Feel Try-Hard",
     "Wearable inspiration rather than runway-only fantasy.",
     "https://www.whowhatwear.com"),
    ("A Page Worth Following for Interior Inspiration",
     "The kind of rooms that feel achievable, not just photogenic.",
     "https://www.architecturaldigest.com"),
    ("An Apartment Worth Stealing Ideas From",
     "Small-space solutions that don't require a full renovation budget.",
     "https://www.apartmenttherapy.com"),
    ("The Travel Guide Site Worth Trusting",
     "Detailed enough to actually plan from, not just admire.",
     "https://www.lonelyplanet.com"),
    ("A Resource for Trips You Haven't Planned Yet",
     "Good for the 'somewhere unusual' phase of planning, before the logistics start.",
     "https://www.atlasobscura.com"),
    ("The Site for Finding Places Everyone Else Missed",
     "Reviews from people who actually went, not just people who wanted to be seen going.",
     "https://www.tripadvisor.com"),
    ("A Travel Blog Worth Following Before Your Next Trip",
     "Practical enough to actually change how a trip gets planned.",
     "https://www.nomadicmatt.com"),
    ("The Page Worth Checking Before Booking Anything",
     "A five-minute habit that's saved more than a few disappointing trips.",
     "https://www.tripadvisor.com"),
    ("A Site for When Motivation Runs Out Mid-Project",
     "Small, concrete advice rather than vague inspiration.",
     "https://jamesclear.com"),
]

NOTE = [
    ("The Two-Minute Rule That Actually Works",
     "If it takes less than two minutes, just do it now — fewer things pile up than expected.",
     wiki("Getting Things Done")),
    ("A Small Habit That Changed More Than Expected",
     "Nothing dramatic — just one thing done consistently instead of many things done rarely.",
     "https://jamesclear.com"),
    ("The Note App Trick Worth Stealing",
     "One inbox for everything, sorted later — fewer half-finished lists everywhere else.",
     "https://www.notion.so"),
    ("A Tiny Kitchen Tool That's Worth the Drawer Space",
     "Small, cheap, and somehow used almost every single day since.",
     seriouseats("kitchen tools worth buying")),
    ("The Playlist Trick for Falling Asleep Faster",
     "Same one, every night — the familiarity does more work than the music itself.",
     "https://open.spotify.com"),
    ("A Reminder Worth Keeping Somewhere Visible",
     "Not profound, just easy to forget without something to keep it in view.",
     "https://www.themarginalian.org"),
    ("The Quote I Keep Coming Back To",
     "Short enough to remember, true enough to still matter years later.",
     "https://www.goodreads.com/quotes"),
    ("A Rule for Slow Mornings Worth Adopting",
     "Nothing urgent for the first twenty minutes — harder than it sounds, worth it anyway.",
     wiki("Slow movement (culture)")),
    ("The One Thing Worth Doing Before Bed",
     "Screens off a little earlier than feels necessary — the difference shows up the next day.",
     "https://www.sleepfoundation.org"),
    ("A Small Ritual Worth Protecting",
     "Five minutes, same time every day — small enough to actually keep.",
     "https://www.themarginalian.org"),
    ("The Best Way to Actually Finish a Book",
     "One at a time, not four half-read ones stacked on the nightstand.",
     "https://www.goodreads.com"),
    ("A Discovery That Made Grocery Shopping Easier",
     "One running list on the phone instead of trying to remember everything at the store.",
     "https://www.realsimple.com"),
    ("The App That Quietly Fixed My Mornings",
     "Not flashy — just consistent enough to stop mornings from feeling chaotic.",
     "https://www.todoist.com"),
    ("A Podcast Worth Starting From Episode One",
     "Better in order — the early episodes set up things that pay off much later.",
     "https://podcasts.apple.com"),
    ("The Museum Trick Nobody Tells You",
     "Go on a weekday afternoon — same collection, a fraction of the crowd.",
     atlasobscura("museum")),
    ("A Font Worth Knowing the Name Of",
     "Once you notice it, it shows up everywhere — in the best way.",
     "https://fonts.google.com"),
    ("The Word I Didn't Know I Needed",
     "One of those words that describes something you'd never quite been able to name.",
     "https://en.wiktionary.org"),
    ("A Color Combination Worth Stealing for a Room",
     "Simple enough to copy without needing a full redesign budget.",
     "https://www.apartmenttherapy.com"),
    ("The Trick for Keeping Herbs Alive Longer",
     "Small change in how they're stored — noticeably longer before they wilt.",
     seriouseats("how to store fresh herbs")),
    ("A Small Design Detail Worth Noticing",
     "Easy to miss, and once you see it you can't stop noticing it everywhere else.",
     "https://www.architecturaldigest.com"),
    ("The Museum Worth Planning a Trip Around",
     "Not a side stop — worth being the actual reason for the trip.",
     atlasobscura("museum worth visiting")),
    ("A Simple Rule for Better Photos on Your Phone",
     "One small compositional habit that makes almost everything look more intentional.",
     wiki("Rule of thirds")),
]

CATEGORIES = [
    ("recipe", RECIPE, None, None),
    ("place", PLACE, "location", None),
    ("song", SONG, None, "artist"),
    ("movie", MOVIE, None, None),
    ("link", LINK, None, None),
    ("note", NOTE, None, None),
]

def sql_escape(s):
    return s.replace("'", "''")

def build_rows():
    """Round-robin interleave across categories so Explore's default sort (published_at desc)
    naturally mixes types instead of clustering all of one type together."""
    lists = [(name, list(items)) for name, items, _loc, _artist in CATEGORIES]
    rows = []
    while any(items for _, items in lists):
        for name, items in lists:
            if items:
                rows.append((name, items.pop(0)))
    return rows

def validate(rows):
    errors = []
    seen_ids = set()
    url_re = re.compile(r"^https://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}(/.*)?$")
    for idx, (ctype, entry) in enumerate(rows):
        title, desc, url = entry[0], entry[1], entry[2]
        rid = f"svoj-seed-{idx+1:04d}"
        if rid in seen_ids:
            errors.append(f"duplicate id {rid}")
        seen_ids.add(rid)
        if not title or len(title) < 8:
            errors.append(f"{rid}: title too short/missing: {title!r}")
        if not desc or len(desc) < 15:
            errors.append(f"{rid}: description too short/missing: {desc!r}")
        if not url_re.match(url):
            errors.append(f"{rid}: url doesn't look like a real https URL: {url!r}")
        if ctype not in ("recipe", "place", "song", "movie", "link", "note"):
            errors.append(f"{rid}: unknown type {ctype!r}")
    return errors

def emit_sql(rows):
    base = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
    lines = []
    lines.append("-- Editorial seed content for the official @svoj account — generated by")
    lines.append("-- scripts/generate_editorial_seed_sql.py. Do not hand-edit; edit the generator")
    lines.append("-- and re-run it instead. See docs/EDITORIAL_SEED.md for the full runbook.")
    lines.append("--")
    lines.append("-- PREREQUISITES (see docs/EDITORIAL_SEED.md for details):")
    lines.append("--   1. An @svoj Supabase Auth user already exists (created once via the dashboard),")
    lines.append(f"--      using the email {SVOJ_EMAIL}.")
    lines.append("--   2. public.usernames exists (see docs/USERNAMES_TABLE.md).")
    lines.append("--   3. is_editorial column exists on public_journal_moments (see JOURNAL_PUBLIC_TABLE.md).")
    lines.append("--")
    lines.append("-- Safe to re-run: every insert upserts by its stable id, so running this migration")
    lines.append("-- again (e.g. after fixing a typo above) never creates duplicate rows.")
    lines.append("")
    lines.append("do $$")
    lines.append("declare")
    lines.append("  svoj_id uuid;")
    lines.append("begin")
    lines.append(f"  select id into svoj_id from auth.users where email = '{SVOJ_EMAIL}';")
    lines.append("  if svoj_id is null then")
    lines.append(f"    raise exception 'No auth.users row for {SVOJ_EMAIL} — create the @svoj account first, see docs/EDITORIAL_SEED.md';")
    lines.append("  end if;")
    lines.append("")
    lines.append("  insert into public.usernames (username, user_id)")
    lines.append("  values ('svoj', svoj_id)")
    lines.append("  on conflict (user_id) do update set username = excluded.username;")
    lines.append("")

    for idx, (ctype, entry) in enumerate(rows):
        title, desc, url = entry[0], entry[1], entry[2]
        rid = f"svoj-seed-{idx+1:04d}"
        published_at = (base - timedelta(hours=idx)).strftime("%Y-%m-%d %H:%M:%S+00")
        artist_sql = "null"
        if ctype == "song" and len(entry) > 3 and entry[3]:
            artist_sql = "'" + sql_escape(entry[3]) + "'"

        # Client rendering quirk this seed data must match exactly: for type='place', the
        # detail view's "Open Map" link reads row.location.url, NOT row.external_url (see
        # journalOpenExploreDetail() in index.html — journalMomentLinkValue() does the same for
        # a user's own moments). external_url stays null for place rows; every other type keeps
        # its link in external_url, matching what the real client-created form would produce.
        if ctype == "place":
            location_json = json.dumps({"name": title, "url": url})
            location_sql = "'" + sql_escape(location_json) + "'::jsonb"
            external_url_sql = "null"
        else:
            location_sql = "null"
            external_url_sql = "'" + sql_escape(url) + "'"

        lines.append(f"  insert into public.public_journal_moments")
        lines.append(f"    (id, user_id, author, type, title, description, image, thumb, external_url, location, artist, is_editorial, created_at, updated_at, published_at)")
        lines.append(f"  values (")
        lines.append(f"    '{rid}', svoj_id, '@svoj', '{ctype}',")
        lines.append(f"    '{sql_escape(title)}',")
        lines.append(f"    '{sql_escape(desc)}',")
        lines.append(f"    null, null,")
        lines.append(f"    {external_url_sql},")
        lines.append(f"    {location_sql}, {artist_sql}, true,")
        lines.append(f"    timestamptz '{published_at}', timestamptz '{published_at}', timestamptz '{published_at}'")
        lines.append(f"  )")
        lines.append(f"  on conflict (id) do update set")
        lines.append(f"    author = excluded.author, type = excluded.type, title = excluded.title,")
        lines.append(f"    description = excluded.description, external_url = excluded.external_url,")
        lines.append(f"    location = excluded.location, artist = excluded.artist,")
        lines.append(f"    is_editorial = excluded.is_editorial, updated_at = now();")
        lines.append("")

    lines.append("end $$;")
    lines.append("")
    return "\n".join(lines)

def main():
    rows = build_rows()
    errors = validate(rows)
    print(f"Generated {len(rows)} rows across {len(CATEGORIES)} categories.")
    for name, items, _loc, _artist in CATEGORIES:
        pass
    counts = {}
    for ctype, _entry in rows:
        counts[ctype] = counts.get(ctype, 0) + 1
    print("Per-type counts:", counts)
    if errors:
        print(f"VALIDATION FAILED — {len(errors)} error(s):")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    sql = emit_sql(rows)
    with open(OUT_PATH, "w") as f:
        f.write(sql)
    print(f"Wrote {OUT_PATH} ({len(sql)} bytes).")

if __name__ == "__main__":
    main()
