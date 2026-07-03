# Business Posts Automation

Automatically generates and publishes business social-media posts on a schedule.

**Project status, roadmap and the new-client onboarding recipe live in
[STATUS.md](STATUS.md). The day-to-day guide is [USER_MANUAL.md](USER_MANUAL.md)
(also built into the dashboard under User Manual).**

**Multi-company:** the dashboard ships with an **Admin portal**
(`docs/admin.html`) that manages every business you automate - each company
gets its own copy of this repo (created from the portal in one click), its own
dashboard, content, captions and secrets. Captions and contact details are
configured per company in `config.yaml` (`captions:` section), so no code
changes are ever needed for a new client.

- **Content generation** — posts are written by Claude (Anthropic API) using your
  business profile in `config.yaml`. If no API key is configured, it falls back to
  the template posts in `config.yaml`.
- **Publishing** — supports Facebook Pages, Instagram (business accounts),
  LinkedIn, X (Twitter), and Telegram. Each platform is optional and activates
  automatically when its credentials are present.
- **Scheduling** — a GitHub Actions workflow (`.github/workflows/post.yml`) runs
  Monday/Wednesday/Friday at 09:00 UTC. No server needed.
- **History** — published posts are recorded in `data/history.json` so topics
  don't repeat.

## Quick start

1. Follow **[SETUP.md](SETUP.md)** to create the accounts/apps and collect the
   API credentials you need.
2. Add the credentials as **GitHub repository secrets** (for scheduled posting)
   or to a local `.env` file (for running on your machine).
3. Edit `config.yaml` with your business name, description, tone, and topics.
4. Test locally:

   ```bash
   pip install -r requirements.txt
   cp .env.example .env      # then fill in your keys
   python -m src.main platforms   # show which platforms are configured
   python -m src.main preview     # generate posts without publishing
   python -m src.main post        # generate and publish
   ```

Once the secrets are set in GitHub, posting happens automatically on the
schedule. You can also trigger a run manually from the repo's **Actions** tab
("Publish business posts" → *Run workflow*).

## Dashboard (GitHub Pages)

A no-backend, single-page dashboard lives in `docs/index.html`, with a left
menu showing one section at a time:

- **Dashboard** — today's numbers, the activity log (every publish attempt
  with the platform's full error text on failure, `data/activity.json`), and
  recent workflow runs.
- **Scheduled Posts** — the queue (`data/queue.json`): everything waiting to
  publish, cancellable per item, plus "process due posts now".
- **Auto Posts** — the campaigns/months described below, with bulk upload.
- **Companies** — switch between the businesses you manage; each card has a
  **Guided setup** wizard that connects GitHub, Facebook (permanent Page
  token) and Instagram (auto-upgraded long-lived token) with verification at
  every step.
- **Admin** — "Add Company" creates a new client's repository automatically
  (default branch `main`, personalized config, cleared starter data).
- **User Manual / Setup Instructions** — the built-in guides.
- **Settings** — the GitHub connection (repo must be **Public** so Instagram
  can fetch the images).

**Auto Posts campaigns (hands-free posting)** — 
create named campaign folders (each with its own start date) and drop
images/videos in; they post themselves. A **day** is any folder containing a
`Post`/`Story` subfolder, at any depth and in any case, so your existing folder
tree works as-is:

```
content/William Collins Ghost 1/Month 1/Day 1/Post/    -> feed posts on the campaign start date
content/William Collins Ghost 1/Month 1/Day 1/Story/   -> stories on the start date
content/William Collins Ghost 1/Month 1/Day 2/...       -> the next day, and so on
content/Another Campaign/Day 1/posts/                   -> add as many campaigns as you like
```

Scheduling is controlled **per month**: in the dashboard each month (batch) has
its own checkbox, start date, and platform selection (Instagram / Facebook) -
only checked months post, day 1 on that month's start date, day 2 the
next day, and so on (days ordered naturally, "Day 2" before "Day 10"). Stored
in `data/campaigns.json` under each campaign's `batches`.
Multiple files in one folder
spread across the day automatically: 2 files post 6h apart, 3 files 4h apart,
4+ files 3h apart. Images are converted to JPEG and sized automatically
(`.webp`/`.png` are fine; feed keeps its aspect ratio within Instagram's limits,
story 1080x1920). Captions come from a
matching `photo1.txt`, a folder `caption.txt` (a randomized hashtag block is
appended if your text has none), or a **unique randomized Gwalava caption** is
written for each post — brand tags, furniture-fittings niche tags, and
high-reach viral tags, never repeating back-to-back (`src/captions.py`). Every
15 minutes the scheduler (`scheduler.yml`) converts new images, queues them
(visible/cancellable in the dashboard Queue), posts what is due, and deletes
each file after posting. Two safety valves protect the account: slots more
than 24h in the past are not queued (a wrong start date can't flood the feed),
and at most 20 posts go out per rolling 24h (Instagram's API allows ~25;
override with the `IG_DAILY_CAP` env var). See `content/README.md` for
details.

**Facebook cross-posting** — set the `FACEBOOK_PAGE_ID` and
`FACEBOOK_PAGE_ACCESS_TOKEN` secrets (see **[SETUP.md](SETUP.md)** §3) and
**every** item posted to Instagram is automatically mirrored to your Facebook
Page in its matching format: feed photos as Page photos, Reels as Page videos,
and Instagram Stories as real **Facebook Page Stories** (they appear in the
Page's Stories ring and expire after 24 hours, exactly like Instagram). It is
best-effort — a Facebook error is recorded on the queue item but never blocks
Instagram.


**Bulk upload and auto-sort** — under *Auto Posts*: pick a pile of unsorted
images, choose the campaign and the target month (existing months continue
their own day numbering; new months start at Day 1), choose how many feed
posts and stories go in each day (2 or 3), and it sizes them, sorts them into
`Month N/Day N/Post|Story` folders, and commits everything in one commit via
the Git Data API. New campaigns and months are registered automatically,
unchecked, until you set the month's date and tick it.

**Tests** — `python -m pytest` runs the suite in `tests/` (image conversion,
folder scheduling, queue posting/retries, Instagram API parameters, caption
generation). CI runs it on every push via `.github/workflows/tests.yml`.

It talks directly to the GitHub API using a fine-grained token you paste in
(stored only in your browser). To use it:

1. Create a **fine-grained PAT** (GitHub → Settings → Developer settings →
   Fine-grained tokens) scoped to this repo with **Actions**, **Contents**, and
   **Secrets** all set to Read and write.
2. Open the dashboard and paste the token under **Settings → Save**.

**Hosting:** repo **Settings → Pages → Source: Deploy from a branch**, pick the
default branch and the `/docs` folder. The dashboard is then live at
`https://OWNER.github.io/REPO/`. (Or open `docs/index.html` locally; it works
identically since it only calls the GitHub API.)

Run a specific flow from the command line too:

```bash
python -m src.main post --flow promo
```

## Commands

| Command | What it does |
|---|---|
| `python -m src.main platforms` | List each platform and whether it's configured |
| `python -m src.main preview` | Generate post text for every enabled platform and print it (nothing is published) |
| `python -m src.main post` | Generate and publish to every enabled platform |
| `python -m src.main post --platforms telegram,facebook` | Publish only to the listed platforms |

## Project layout

```
config.yaml               Business profile, topics, tone, template posts
src/config.py             Loads .env / environment + config.yaml
src/content_generator.py  Claude-powered post writer (with template fallback)
src/history.py            Duplicate-avoidance history (data/history.json)
src/platforms/            One publisher per social network
src/main.py               CLI entry point
.github/workflows/post.yml  Scheduler
```
