-- SVOJ money: shared budgets (generic, works for any two or more users)
-- Run this once in Supabase → SQL Editor → New query → paste all of this → Run.
-- Safe to re-run: every statement is guarded so it won't error on a second run.

-- 1) profiles: one row per signed-up user, holding the display name they typed
--    in SVOJ money. Needed so a shared budget can show real names instead of
--    made-up ones -- nothing here is guessable or browsable by other users.
create table if not exists public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null default 'User',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.profiles enable row level security;

drop policy if exists "profiles readable by any signed-in user" on public.profiles;
create policy "profiles readable by any signed-in user"
  on public.profiles for select
  using (auth.role() = 'authenticated');

drop policy if exists "users insert own profile" on public.profiles;
create policy "users insert own profile"
  on public.profiles for insert
  with check (auth.uid() = user_id);

drop policy if exists "users update own profile" on public.profiles;
create policy "users update own profile"
  on public.profiles for update
  using (auth.uid() = user_id);

-- 2) shared_budgets: one row per shared budget. Anyone can create one; nobody
--    can browse the list (see the join_shared_budget function below for how
--    joining works instead -- by code only, never by scanning this table).
create table if not exists public.shared_budgets (
  id uuid primary key default gen_random_uuid(),
  invite_code text not null unique,
  name text not null default 'Общий бюджет',
  created_by uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);
alter table public.shared_budgets enable row level security;

-- 3) shared_budget_members: who belongs to which budget.
create table if not exists public.shared_budget_members (
  budget_id uuid not null references public.shared_budgets(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  joined_at timestamptz not null default now(),
  primary key (budget_id, user_id)
);
alter table public.shared_budget_members enable row level security;

-- Helper used by RLS policies below. SECURITY DEFINER so it can check
-- membership without the policies on shared_budget_members recursively
-- calling themselves (a classic Postgres RLS trap).
create or replace function public.is_member_of_budget(b_id uuid)
returns boolean
language sql
security definer
stable
as $$
  select exists (
    select 1 from public.shared_budget_members m
    where m.budget_id = b_id and m.user_id = auth.uid()
  );
$$;

drop policy if exists "members can view their budgets" on public.shared_budgets;
create policy "members can view their budgets"
  on public.shared_budgets for select
  using (public.is_member_of_budget(id));

drop policy if exists "members can view membership of their budgets" on public.shared_budget_members;
create policy "members can view membership of their budgets"
  on public.shared_budget_members for select
  using (public.is_member_of_budget(budget_id));

-- 4) shared_budget_transactions: the actual expense/income rows inside a
--    shared budget. Personal (is_common = false) rows are editable only by
--    their owner; common rows (is_common = true) are editable by any member.
--    Everyone in the budget can always SEE every row.
create table if not exists public.shared_budget_transactions (
  id uuid primary key default gen_random_uuid(),
  budget_id uuid not null references public.shared_budgets(id) on delete cascade,
  owner_id uuid not null references auth.users(id) on delete cascade,
  kind text not null check (kind in ('expense','income')),
  is_common boolean not null default false,
  amount numeric not null,
  currency text not null default 'EUR',
  category text,
  merchant text,
  note text,
  date date not null,
  time text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.shared_budget_transactions enable row level security;

drop policy if exists "members can view all transactions in their budget" on public.shared_budget_transactions;
create policy "members can view all transactions in their budget"
  on public.shared_budget_transactions for select
  using (public.is_member_of_budget(budget_id));

drop policy if exists "members can insert their own transactions" on public.shared_budget_transactions;
create policy "members can insert their own transactions"
  on public.shared_budget_transactions for insert
  with check (public.is_member_of_budget(budget_id) and owner_id = auth.uid());

drop policy if exists "owner or any member for common rows can update" on public.shared_budget_transactions;
create policy "owner or any member for common rows can update"
  on public.shared_budget_transactions for update
  using (public.is_member_of_budget(budget_id) and (owner_id = auth.uid() or is_common));

drop policy if exists "owner or any member for common rows can delete" on public.shared_budget_transactions;
create policy "owner or any member for common rows can delete"
  on public.shared_budget_transactions for delete
  using (public.is_member_of_budget(budget_id) and (owner_id = auth.uid() or is_common));

-- 5) create_shared_budget(): call this to start a new shared budget. Creates
--    the budget, generates a unique SVOJ-XXXX code, and adds the caller as
--    the first member -- all in one atomic step.
create or replace function public.create_shared_budget(p_name text default 'Общий бюджет')
returns table(budget_id uuid, invite_code text)
language plpgsql
security definer
as $$
declare
  v_code text;
  v_id uuid;
begin
  loop
    v_code := 'SVOJ-' || upper(substr(md5(random()::text || clock_timestamp()::text), 1, 4));
    exit when not exists (select 1 from public.shared_budgets sb where sb.invite_code = v_code);
  end loop;
  insert into public.shared_budgets(invite_code, name, created_by)
    values (v_code, p_name, auth.uid())
    returning id into v_id;
  insert into public.shared_budget_members(budget_id, user_id) values (v_id, auth.uid());
  return query select v_id, v_code;
end;
$$;

-- 6) join_shared_budget(): call this with a code to join. This is the ONLY
--    way to discover a budget by its code -- there is no SELECT policy that
--    lets anyone browse shared_budgets by code, only this atomic function.
create or replace function public.join_shared_budget(p_code text)
returns table(budget_id uuid, budget_name text)
language plpgsql
security definer
as $$
declare
  v_budget public.shared_budgets%rowtype;
begin
  select * into v_budget from public.shared_budgets sb where sb.invite_code = upper(trim(p_code));
  if v_budget.id is null then
    raise exception 'Invalid invite code';
  end if;
  insert into public.shared_budget_members(budget_id, user_id)
    values (v_budget.id, auth.uid())
    on conflict (budget_id, user_id) do nothing;
  return query select v_budget.id, v_budget.name;
end;
$$;

-- 7) budget_participants(): convenience view-like function returning every
--    member of a budget together with their display name, for the UI.
create or replace function public.budget_participants(b_id uuid)
returns table(user_id uuid, display_name text, joined_at timestamptz)
language sql
security definer
stable
as $$
  select p.user_id, p.display_name, m.joined_at
  from public.shared_budget_members m
  join public.profiles p on p.user_id = m.user_id
  where m.budget_id = b_id and public.is_member_of_budget(b_id);
$$;
