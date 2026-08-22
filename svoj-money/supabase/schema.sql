-- =============================================================================
-- SVOJ Money -- isolated database schema
--
-- Run this ONCE, in full, in the SQL Editor of a NEW, DEDICATED Supabase
-- project created just for SVOJ Money (Dashboard -> SQL Editor -> New query
-- -> paste this whole file -> Run). Do NOT run this against the SVOJ planner
-- app's existing Supabase project -- the whole point is that Money gets its
-- own project, its own auth.users, and its own tables, so a bug or RLS gap
-- in one app can never expose the other app's data.
--
-- After running this, go to Project Settings -> API and copy this project's
-- "Project URL" and "anon public" key into SUPABASE_URL / SUPABASE_ANON_KEY
-- near the top of index.html's <script> block.
--
-- Every table below has Row Level Security enabled, and every policy scopes
-- rows by auth.uid() (the signed-in user's own id, verified server-side by
-- Supabase from the request's JWT -- not something the client can spoof).
-- Nothing in this app relies on client-side filtering for security.
-- =============================================================================

create extension if not exists pgcrypto;

-- -----------------------------------------------------------------------------
-- app_data: generic per-user key/value store. Everything that isn't part of a
-- shared budget (expenses, income, categories, budgets, usage stats, settings)
-- lives here as one JSON blob per data_key, scoped to the owning user.
-- -----------------------------------------------------------------------------
create table if not exists public.app_data (
  user_id     uuid not null references auth.users(id) on delete cascade,
  data_key    text not null,
  data        jsonb,
  updated_at  timestamptz not null default now(),
  primary key (user_id, data_key)
);

alter table public.app_data enable row level security;

create policy "app_data: owner full access"
  on public.app_data
  for all
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

grant select, insert, update, delete on public.app_data to authenticated;

-- -----------------------------------------------------------------------------
-- profiles: one row per user, holding just the display name shown to other
-- members of a shared budget. A user can only read/write their OWN profile
-- row directly -- other members' names are exposed only through the
-- budget_participants() function below, and only for budgets you're in.
-- -----------------------------------------------------------------------------
create table if not exists public.profiles (
  user_id       uuid primary key references auth.users(id) on delete cascade,
  display_name  text,
  updated_at    timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "profiles: owner full access"
  on public.profiles
  for all
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

grant select, insert, update, delete on public.profiles to authenticated;

-- -----------------------------------------------------------------------------
-- shared_budgets / shared_budget_members: a shared budget is created by one
-- user and joined by others via a short invite code. Membership rows are
-- never inserted directly by the client -- only through the SECURITY DEFINER
-- functions further down, which enforce "you must know the invite code" (or
-- "you must be the creator") before anyone is added.
-- -----------------------------------------------------------------------------
create table if not exists public.shared_budgets (
  id           uuid primary key default gen_random_uuid(),
  name         text not null,
  invite_code  text not null unique,
  owner_id     uuid not null references auth.users(id) on delete cascade,
  created_at   timestamptz not null default now()
);

create table if not exists public.shared_budget_members (
  budget_id  uuid not null references public.shared_budgets(id) on delete cascade,
  user_id    uuid not null references auth.users(id) on delete cascade,
  joined_at  timestamptz not null default now(),
  primary key (budget_id, user_id)
);

alter table public.shared_budgets enable row level security;
alter table public.shared_budget_members enable row level security;

-- Helper: is `uid` a member of budget `b_id`? SECURITY DEFINER so it can read
-- shared_budget_members without triggering that table's own RLS policy again
-- (which would otherwise call this same function -> infinite recursion).
-- This is the standard, safe Supabase pattern for membership-gated RLS.
create or replace function public.is_budget_member(b_id uuid, uid uuid)
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select exists(
    select 1 from public.shared_budget_members
    where budget_id = b_id and user_id = uid
  );
$$;

revoke all on function public.is_budget_member(uuid, uuid) from public;
grant execute on function public.is_budget_member(uuid, uuid) to authenticated;

create policy "shared_budgets: members and owner can view"
  on public.shared_budgets
  for select
  to authenticated
  using (owner_id = auth.uid() or public.is_budget_member(id, auth.uid()));

create policy "shared_budget_members: members can view their budgets' rosters"
  on public.shared_budget_members
  for select
  to authenticated
  using (public.is_budget_member(budget_id, auth.uid()));

-- Deliberately NOT granting insert/update/delete on either table to
-- `authenticated` -- all writes go through create_shared_budget() /
-- join_shared_budget() below, which run as the function owner and enforce
-- their own rules (know the code, or be the creator) before writing.
grant select on public.shared_budgets to authenticated;
grant select on public.shared_budget_members to authenticated;

-- -----------------------------------------------------------------------------
-- shared_budget_transactions: expenses/income posted inside a shared budget.
-- Permission model (matches the app's canEditSharedTx()):
--   - any member can see every transaction in a budget they belong to
--   - a member can create their own transactions
--   - a member can edit/delete their OWN transaction, or any transaction
--     marked is_common (shared/joint spend any member can maintain)
--   - a member can NEVER edit or delete another member's personal expense
-- -----------------------------------------------------------------------------
create table if not exists public.shared_budget_transactions (
  id          uuid primary key default gen_random_uuid(),
  budget_id   uuid not null references public.shared_budgets(id) on delete cascade,
  owner_id    uuid not null references auth.users(id) on delete cascade,
  kind        text not null check (kind in ('expense','income')),
  is_common   boolean not null default false,
  amount      numeric not null check (amount > 0),
  currency    text not null default 'EUR',
  category    text,
  note        text,
  date        date not null,
  time        text,
  created_at  timestamptz not null default now()
);

alter table public.shared_budget_transactions enable row level security;

create policy "shared_tx: members can view"
  on public.shared_budget_transactions
  for select
  to authenticated
  using (public.is_budget_member(budget_id, auth.uid()));

create policy "shared_tx: members can insert their own"
  on public.shared_budget_transactions
  for insert
  to authenticated
  with check (
    public.is_budget_member(budget_id, auth.uid())
    and owner_id = auth.uid()
  );

create policy "shared_tx: owner or common can update"
  on public.shared_budget_transactions
  for update
  to authenticated
  using (
    public.is_budget_member(budget_id, auth.uid())
    and (owner_id = auth.uid() or is_common)
  )
  with check (
    public.is_budget_member(budget_id, auth.uid())
    and (owner_id = auth.uid() or is_common)
  );

create policy "shared_tx: owner or common can delete"
  on public.shared_budget_transactions
  for delete
  to authenticated
  using (
    public.is_budget_member(budget_id, auth.uid())
    and (owner_id = auth.uid() or is_common)
  );

grant select, insert, update, delete on public.shared_budget_transactions to authenticated;

-- -----------------------------------------------------------------------------
-- Invite codes + the two RPCs the client actually calls to create/join a
-- shared budget. Both are SECURITY DEFINER so they can insert into
-- shared_budgets / shared_budget_members despite those tables having no
-- direct insert grant for `authenticated` -- the function body is the only
-- thing allowed to add members, and it only does so for the creator or for
-- someone who supplied a correct invite code.
-- -----------------------------------------------------------------------------
create or replace function public.generate_invite_code()
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  chars text := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; -- no 0/O/1/I ambiguity
  code text;
  exists_already boolean;
begin
  loop
    code := 'SVOJ-';
    for i in 1..4 loop
      code := code || substr(chars, floor(random() * length(chars) + 1)::int, 1);
    end loop;
    select exists(select 1 from public.shared_budgets where invite_code = code) into exists_already;
    exit when not exists_already;
  end loop;
  return code;
end;
$$;

revoke all on function public.generate_invite_code() from public;

create or replace function public.create_shared_budget(p_name text)
returns table(budget_id uuid, invite_code text)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id uuid;
  v_code text;
begin
  if auth.uid() is null then
    raise exception 'not authenticated';
  end if;
  v_code := public.generate_invite_code();
  insert into public.shared_budgets (name, invite_code, owner_id)
  values (coalesce(nullif(trim(p_name), ''), 'Shared budget'), v_code, auth.uid())
  returning id into v_id;
  insert into public.shared_budget_members (budget_id, user_id) values (v_id, auth.uid());
  return query select v_id, v_code;
end;
$$;

revoke all on function public.create_shared_budget(text) from public;
grant execute on function public.create_shared_budget(text) to authenticated;

create or replace function public.join_shared_budget(p_code text)
returns table(budget_id uuid, budget_name text)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id uuid;
  v_name text;
begin
  if auth.uid() is null then
    raise exception 'not authenticated';
  end if;
  select id, name into v_id, v_name
  from public.shared_budgets
  where upper(invite_code) = upper(trim(p_code));

  if v_id is null then
    raise exception 'invalid invite code';
  end if;

  -- Written as insert-if-missing rather than "on conflict (budget_id, user_id)"
  -- because this function's OUT parameter is itself named budget_id, which
  -- makes a bare, unqualified column list in the conflict target ambiguous
  -- (PL/pgSQL can't tell it apart from the OUT variable of the same name).
  insert into public.shared_budget_members (budget_id, user_id)
  select v_id, auth.uid()
  where not exists (
    select 1 from public.shared_budget_members m
    where m.budget_id = v_id and m.user_id = auth.uid()
  );

  return query select v_id, v_name;
end;
$$;

revoke all on function public.join_shared_budget(text) from public;
grant execute on function public.join_shared_budget(text) to authenticated;

-- Returns the display name of every member of a budget -- but ONLY if the
-- caller is themselves a member of it. This is how the app shows "Eva /
-- Marko" (or whatever names the real members chose) without granting broad
-- read access to the profiles table.
create or replace function public.budget_participants(b_id uuid)
returns table(user_id uuid, display_name text)
language plpgsql
security definer
set search_path = public
as $$
begin
  if not public.is_budget_member(b_id, auth.uid()) then
    raise exception 'not a member of this budget';
  end if;
  return query
    select m.user_id, coalesce(p.display_name, 'Member')
    from public.shared_budget_members m
    left join public.profiles p on p.user_id = m.user_id
    where m.budget_id = b_id;
end;
$$;

revoke all on function public.budget_participants(uuid) from public;
grant execute on function public.budget_participants(uuid) to authenticated;

-- =============================================================================
-- Done. Quick sanity check you can run afterwards (as any signed-in user, via
-- the client or the SQL editor's "Run as" impersonation): querying
-- `select * from app_data` should only ever return YOUR OWN rows, never
-- another user's, with no WHERE clause needed -- that's RLS doing its job.
-- =============================================================================
