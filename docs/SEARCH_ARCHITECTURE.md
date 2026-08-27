# Explore search — current state and the hybrid search spec

## What exists today

A real, working plain-text search box in Explore (`#journalExploreSearch`, wired in
`buildJournalExploreView()`/`journalExploreMatches()` in `index.html`). It filters the already-
fetched public rows client-side by substring match against `title`, `description`, the type
label, and `artist` — no network call, no AI, nothing beyond what a normal `Array.filter` does.
It only ever operates on Explore's public rows (`public_journal_moments`), which is the same set
Explore already displays — it can't see and never touches private Journal content.

**This is a deliberate, working baseline, not a placeholder.** Grep across the codebase before
this pass found zero prior search/embeddings/vector code anywhere — despite it being referenced
as "the search functionality we discussed," nothing had actually been built yet. Rather than
leave Explore with no search at all, this plain-text version ships now; everything below is the
concrete next step, not a description of something partially built.

## Why hybrid (text + semantic) search isn't built yet

The target behavior — a search for **"chicken recipes"** finding a public moment titled
**"Creamy garlic chicken for Sunday dinner"** even though the literal phrase never appears — needs
vector similarity search over text embeddings. That requires, at minimum:

1. **An embeddings model call** to turn a moment's text (title + description) into a vector at
   publish time, and to turn a search query into a vector at search time.
2. **A vector column + index** on `public_journal_moments` (Postgres `pgvector` extension,
   `embedding vector(N)` column, an `ivfflat`/`hnsw` index) to make similarity search fast.
3. **A server-side function** to do the embedding call — the task's own constraint ("do not make
   AI calls directly from the client") rules out calling an embeddings API from `index.html`
   with a client-exposed key. That means a **Supabase Edge Function** (or equivalent
   server-side endpoint) that the client calls instead, which then calls the embeddings API
   server-side using a secret key.

None of that exists yet, and this session can't create it: same limitation already documented
for `public_journal_moments` and `usernames` (`docs/JOURNAL_PUBLIC_TABLE.md`,
`docs/USERNAMES_TABLE.md`) — schema changes and Edge Functions need your Supabase dashboard
(SQL Editor, Edge Functions deploy), which this session's client-side anon key can't do. This is
also a materially bigger lift than those two tables (a new extension, a new function, an
external API key to provision and keep secret), so it's written up here as a spec rather than
attempted as a partial implementation that couldn't actually be tested end-to-end.

## The spec, for when it's built

### 1. Schema addition to `public_journal_moments`
```sql
create extension if not exists vector;

alter table public.public_journal_moments
  add column if not exists embedding vector(1536); -- dimension matches whichever embeddings model is used

create index if not exists public_journal_moments_embedding_idx
  on public.public_journal_moments using ivfflat (embedding vector_cosine_ops);
```
Private moments (`wp-journal-moments-v1`) are **never** given an embedding column — only public
rows are ever searchable, matching the existing "private never appears in Explore" invariant.

### 2. A Supabase Edge Function, e.g. `embed-and-search`
- On publish (`journalSyncPublic()` in `index.html`, when `m.visibility === 'public'`): instead
  of (or in addition to) the direct `upsert` it already does, call the Edge Function with the
  moment's `title`+`description`; the function calls the embeddings API server-side, writes the
  resulting vector into the same row's `embedding` column.
- On search: the client calls the Edge Function with the query string instead of running a plain
  `select`; the function embeds the query server-side, then runs a single query that combines:
  - a `pgvector` similarity search (`embedding <=> query_embedding`, ordered by distance), and
  - a plain Postgres full-text match (`to_tsvector`/`plainto_tsquery` on title+description) —
  merging both result sets client- or function-side (e.g. reciprocal rank fusion, or just a
  simple "union, dedupe, prefer text-match hits") is the "hybrid" part. Pure vector search alone
  tends to miss exact-phrase/short-query matches that plain text search catches trivially, and
  vice versa for the "chicken recipes" → "garlic chicken" case — using both is why this is
  called hybrid rather than picking one.
- The client (`index.html`) never sees or holds the embeddings API key — only the Edge
  Function's URL/anon-authenticated endpoint, same trust boundary as every other Supabase call
  this app already makes.

### 3. Client-side integration point
`journalExploreMatches(items, query)` in `index.html` is exactly the seam to replace: instead of
(or as a fallback alongside) the local substring filter, call the Edge Function with `query`,
get back a ranked list of moment ids, and render those through the existing
`journalExploreCardHtml`/`journalOpenExploreDetail` — no changes needed to how a result is
displayed, only to how the result set is produced. Keeping the plain-text filter as an automatic
fallback (when the Edge Function is unreachable/not yet deployed) follows the same
graceful-degradation pattern already used for `public_journal_moments` and `usernames`.

### 4. What stays exactly as it is
- Private moments are never embedded, indexed, or searchable — this is additive to the existing
  public-only Explore architecture, not a rework of it.
- No AI call ever originates from the client — every embeddings call happens inside the Edge
  Function, server-side, using a secret key that never reaches the browser.
