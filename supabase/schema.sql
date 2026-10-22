-- YarnFlow community database
-- Run once in the Supabase dashboard: SQL Editor → New query → paste → Run.
-- Public, insert-only table: anyone can browse, publish, and like.
-- Nobody (with the anon key) can edit or delete.

create extension if not exists pgcrypto;

create table if not exists public.makes (
  id          uuid primary key default gen_random_uuid(),
  created_at  timestamptz not null default now(),
  title       text not null check (char_length(title) between 1 and 120),
  author      text check (author is null or char_length(author) <= 60),
  parent_id   uuid references public.makes(id) on delete set null,
  likes       integer not null default 0,
  hidden      boolean not null default false,                       -- moderation switch
  state       jsonb not null check (pg_column_size(state) < 20000)  -- 20 KB per make (real ones are ~1-2 KB)
);

-- Adding to an existing table? Run just this line:
-- alter table public.makes add column if not exists hidden boolean not null default false;

create index if not exists makes_created_at_idx on public.makes (created_at desc);
create index if not exists makes_parent_id_idx  on public.makes (parent_id);

alter table public.makes enable row level security;

drop policy if exists "public read"    on public.makes;
drop policy if exists "public publish" on public.makes;

create policy "public read"    on public.makes for select to anon, authenticated using (not hidden);
create policy "public publish" on public.makes for insert to anon, authenticated
  with check (likes = 0 and hidden = false);  -- can't seed fake like counts or pre-hide

-- Flood control: at most 30 new makes per 10 minutes, site-wide.
-- Legit traffic from a LinkedIn post is well under this; a script hits the wall fast.
create or replace function public.makes_throttle()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if (select count(*) from public.makes where created_at > now() - interval '10 minutes') >= 30 then
    raise exception 'The feed is busy right now — please try again in a few minutes'
      using errcode = 'P0001';
  end if;
  if char_length(coalesce(new.state->>'pattern','')) > 12000 then
    raise exception 'Pattern is too long to publish' using errcode = 'P0001';
  end if;
  return new;
end;
$$;

drop trigger if exists makes_throttle on public.makes;
create trigger makes_throttle before insert on public.makes
  for each row execute function public.makes_throttle();

-- Likes go through an RPC so the anon key never gets UPDATE on the table.
-- Capped at 10,000 per make so a script can't overflow the counter.
create or replace function public.like_make(make_id uuid)
returns integer
language sql
security definer
set search_path = public
as $$
  update public.makes set likes = least(likes + 1, 10000)
  where id = make_id and not hidden returning likes;
$$;

revoke all on function public.like_make(uuid) from public;
grant execute on function public.like_make(uuid) to anon, authenticated;
