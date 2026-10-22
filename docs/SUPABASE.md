# Community database (Supabase)

YarnFlow's Community feed can run on a shared Postgres database hosted by
[Supabase](https://supabase.com) instead of GitHub Issues. Browsing,
publishing and liking then need no account at all.

The app talks to Supabase's REST endpoint (PostgREST) with plain `fetch`,
so there is no SDK, no build step, and it still works from `file://`.

## Setup (one time, ~5 minutes)

1. **Create a project** at <https://supabase.com/dashboard> (free tier is fine).
2. **Create the table.** In the dashboard open *SQL Editor → New query*,
   paste the contents of [`supabase/schema.sql`](../supabase/schema.sql),
   and click **Run**.
3. **Copy your keys.** *Project Settings → API*:
   - *Project URL* (looks like `https://abcdefgh.supabase.co`)
   - *anon public* key (long `eyJ…` string)
4. **Paste them into `index.html`.** Search for `SUPABASE_URL` near the
   `Community database` comment:

   ```js
   const SUPABASE_URL="https://abcdefgh.supabase.co";
   const SUPABASE_ANON_KEY="eyJhbGciOi...";
   ```

5. Reload the page and open **Community**. The note at the top of the modal
   should now say makes are stored in a shared database.

Leave both constants empty to fall back to the GitHub-Issues feed.

## Is it safe to commit the anon key?

Yes. The anon key is Supabase's *publishable* key; it is meant to ship in
client code. What protects the data is row-level security in the schema:

| Who         | select | insert | update | delete |
|-------------|--------|--------|--------|--------|
| anon (web)  | yes    | yes    | no     | no     |

Likes are incremented through the `like_make()` function, which runs with
the table owner's rights but can only add one to `likes`. The browser also
remembers which makes it has liked and won't send a second like for them.

## Schema

| column       | type        | notes                                   |
|--------------|-------------|-----------------------------------------|
| `id`         | uuid        | primary key, auto-generated             |
| `created_at` | timestamptz | default `now()`                         |
| `title`      | text        | 1–120 chars                             |
| `author`     | text        | optional, ≤ 60 chars                    |
| `parent_id`  | uuid        | the make this is a variation of, or null|
| `likes`      | integer     | default 0, capped at 10,000             |
| `hidden`     | boolean     | moderation switch, default false        |
| `state`      | jsonb       | full YarnFlow design, < 20 KB           |

`state` is exactly what *Download .crochet (JSON)* exports, so a row can be
loaded straight back into the app.

## Abuse limits (built into the schema)

- **Flood control:** at most 30 new makes per 10 minutes site-wide. Past
  that, publishing returns "The feed is busy right now". Tune the number in
  `makes_throttle()` if a launch day is busier than expected.
- **Size:** each row's `state` is capped at 20 KB and the pattern text at
  12,000 characters. A real make is 1–2 KB.
- **Likes:** capped at 10,000 per make. The browser also remembers which
  makes it liked.
- **Input hardening:** the app validates every field of a loaded make
  (colour hex, yarn type, hook size, weight index) before applying it, so a
  hand-crafted row cannot break the viewer.

## Moderation

Hide a post without deleting it (*Table Editor → makes → tick `hidden`*),
or with SQL:

```sql
update public.makes set hidden = true where id = '<uuid>';
```

Hidden makes vanish from the feed instantly and can't be liked. Delete for
real with `delete from public.makes where id = '<uuid>';` — variations of a
deleted make are kept and become top-level posts.
