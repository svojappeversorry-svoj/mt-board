-- =============================================================================
-- SVOJ Money -- live isolation verification
--
-- Run this in YOUR new project's SQL Editor to prove, against the real
-- deployed schema, that one account cannot read or write another's data,
-- and that shared-budget permissions are enforced (own data editable,
-- common data editable by any member, another member's personal data
-- never editable). This mirrors the exact test already run locally against
-- schema.sql before you pasted it in -- this script just re-proves it here.
--
-- SETUP (2 minutes, once):
--   1. Dashboard -> Authentication -> Users -> Add user -> create two throwaway
--      test accounts (any email/password, e.g. test-a@example.com /
--      test-b@example.com). This uses Supabase's real user-creation path, so
--      it respects every constraint/trigger the auth system relies on --
--      much safer than inserting rows into auth.users by hand.
--   2. Copy each user's UUID (shown in the Users table) and paste them below,
--      replacing the two placeholder UUIDs.
--   3. Run this whole script. Every check prints an OK notice; anything wrong
--      raises an exception and stops the script immediately.
--   4. When done, delete the two test users from Authentication -> Users --
--      the on delete cascade on every table means all their test rows go
--      with them automatically. Nothing from this script touches any other
--      user's data.
-- =============================================================================

do $$
declare
  -- >>> REPLACE these two with the real UUIDs of your two test users <<<
  user_a uuid := '00000000-0000-0000-0000-00000000000a';
  user_b uuid := '00000000-0000-0000-0000-00000000000b';

  cnt int;
  v_budget_id uuid;
  v_invite_code text;
  v_joined_budget_id uuid;
  v_joined_budget_name text;
  v_b_tx_id uuid;
begin
  if not exists (select 1 from auth.users where id = user_a) then
    raise exception 'user_a (%) does not exist -- create it via Authentication > Users first', user_a;
  end if;
  if not exists (select 1 from auth.users where id = user_b) then
    raise exception 'user_b (%) does not exist -- create it via Authentication > Users first', user_b;
  end if;

  -- ===== As A: write own app_data + profile =====
  perform set_config('request.jwt.claim.sub', user_a::text, true);
  set local role authenticated;

  insert into public.app_data (user_id, data_key, data)
  values (user_a, 'verify-test-key', '{"probe":"a"}');

  insert into public.profiles (user_id, display_name)
  values (user_a, 'Verify Account A')
  on conflict (user_id) do update set display_name = excluded.display_name;

  -- A tries to write under B's user_id -- must be blocked by RLS
  begin
    insert into public.app_data (user_id, data_key, data)
    values (user_b, 'verify-test-key', '{"probe":"sneaky"}');
    raise exception 'SECURITY BUG: A was able to write B''s app_data row';
  exception
    when others then
      if sqlerrm like 'SECURITY BUG%' then raise; end if;
      raise notice 'OK: A blocked from writing B''s app_data (%)', sqlerrm;
  end;

  reset role;

  -- ===== As B: must see ZERO of A's app_data =====
  perform set_config('request.jwt.claim.sub', user_b::text, true);
  set local role authenticated;

  select count(*) into cnt from public.app_data where data_key = 'verify-test-key';
  if cnt <> 0 then
    raise exception 'SECURITY BUG: B can see % of A''s app_data rows', cnt;
  end if;
  raise notice 'OK: B sees zero of A''s app_data rows';

  insert into public.app_data (user_id, data_key, data)
  values (user_b, 'verify-test-key', '{"probe":"b"}');

  insert into public.profiles (user_id, display_name)
  values (user_b, 'Verify Account B')
  on conflict (user_id) do update set display_name = excluded.display_name;

  reset role;

  -- ===== Back as A: sees only its own row, and only its own profile =====
  perform set_config('request.jwt.claim.sub', user_a::text, true);
  set local role authenticated;

  select count(*) into cnt from public.app_data where data_key = 'verify-test-key';
  if cnt <> 1 then
    raise exception 'SECURITY BUG: A sees % app_data rows, expected exactly 1', cnt;
  end if;
  raise notice 'OK: A sees exactly its own app_data row';

  select count(*) into cnt from public.profiles;
  if cnt <> 1 then
    raise exception 'SECURITY BUG: A can see % profile rows (should only see its own)', cnt;
  end if;
  raise notice 'OK: A sees only its own profile row';

  -- ===== A creates a shared budget, B joins by code =====
  select budget_id, invite_code into v_budget_id, v_invite_code
  from public.create_shared_budget('Verify Test Budget');

  reset role;
  perform set_config('request.jwt.claim.sub', user_b::text, true);
  set local role authenticated;

  select budget_id, budget_name into v_joined_budget_id, v_joined_budget_name
  from public.join_shared_budget(v_invite_code);

  if v_joined_budget_id <> v_budget_id then
    raise exception 'SECURITY BUG: join_shared_budget returned the wrong budget';
  end if;
  raise notice 'OK: B joined A''s shared budget via invite code';

  insert into public.shared_budget_transactions (budget_id, owner_id, kind, is_common, amount, currency, category, date)
  values (v_budget_id, user_b, 'expense', false, 50, 'EUR', 'food', current_date)
  returning id into v_b_tx_id;

  select count(*) into cnt from public.budget_participants(v_budget_id);
  if cnt <> 2 then
    raise exception 'SECURITY BUG: budget_participants returned % rows, expected 2', cnt;
  end if;
  raise notice 'OK: budget_participants shows both real members';

  reset role;

  -- ===== As A: can see B's personal tx, but cannot edit/delete it =====
  perform set_config('request.jwt.claim.sub', user_a::text, true);
  set local role authenticated;

  select count(*) into cnt from public.shared_budget_transactions where budget_id = v_budget_id;
  if cnt <> 1 then
    raise exception 'SECURITY BUG: A cannot see B''s shared-budget transaction';
  end if;
  raise notice 'OK: A can see B''s shared-budget transaction';

  update public.shared_budget_transactions set amount = 999 where id = v_b_tx_id;
  get diagnostics cnt = row_count;
  if cnt <> 0 then
    raise exception 'SECURITY BUG: A was able to edit B''s personal transaction';
  end if;
  raise notice 'OK: A blocked from editing B''s personal transaction';

  delete from public.shared_budget_transactions where id = v_b_tx_id;
  get diagnostics cnt = row_count;
  if cnt <> 0 then
    raise exception 'SECURITY BUG: A was able to delete B''s personal transaction';
  end if;
  raise notice 'OK: A blocked from deleting B''s personal transaction';

  reset role;

  -- ===== Cleanup: remove only the rows this script created =====
  delete from public.shared_budget_transactions where budget_id = v_budget_id;
  delete from public.shared_budget_members where budget_id = v_budget_id;
  delete from public.shared_budgets where id = v_budget_id;
  delete from public.app_data where data_key = 'verify-test-key';
  delete from public.profiles where user_id in (user_a, user_b) and display_name like 'Verify Account%';

  raise notice '=== ALL ISOLATION TESTS PASSED ===';
end $$;
