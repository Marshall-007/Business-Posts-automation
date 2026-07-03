# Business Posts Automation

Automatically generates and publishes business social-media posts on a schedule.

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

A no-backend web dashboard lives in `docs/index.html`. It lets you:

- **Add/edit/delete flows** — a *flow* is a saved posting preset (which platforms,
  an optional fixed caption, an optional Instagram image). Flows are stored in
  `data/flows.json` and edited directly through the dashboard.
- **Trigger a run** — "Run standard post" or "Run now" on any flow dispatches the
  GitHub Actions workflow, which publishes for you.
- **See recent runs** — status and links to each workflow run.

**Schedule Instagram posts** — the dashboard also has a *Schedule Instagram posts*
section: add up to three images with captions and a day/time for each. Each image
is squared to 1080x1080 (white padding) and uploaded to the repo; the
`Scheduled Instagram queue` workflow (`scheduler.yml`, runs every 15 min) posts
each one at its chosen time and then deletes the image from the repo. The queue
lives in `data/queue.json`. This requires the repo to be **Public** so Instagram
can fetch the images.

**Content campaigns (hands-free posting)** — instead of uploading through the UI,
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

Day folders are ordered naturally ("Day 2" before "Day 10", "Month 1" before
"Month 2") and assigned consecutive dates from the campaign's start date. Add
campaigns and set each one's start date and daily times in the dashboard's
*Content campaigns* section (stored in `data/campaigns.json`), and enable each.
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
Page: feed photos as Page photos, Reels as Page videos, stories as Page posts.
It is best-effort — a Facebook error is recorded on the queue item but never
blocks Instagram.

**Bulk upload and auto-sort** — the dashboard's *Content campaigns* section has a
*Bulk upload and auto-sort* tool: pick a pile of unsorted images, choose how many
feed posts and stories go in each day (2 or 3), and it sizes them (feed
1080x1080, story 1080x1920), sorts them into `day1/day2/...` `posts`/`stories`
folders for the chosen campaign, and commits them all in one commit via the Git
Data API. A new campaign name is created automatically. Then set the campaign's
start date and enable it.

**Tests** — `python -m pytest` runs the suite in `tests/` (image conversion,
folder scheduling, queue posting/retries, Instagram API parameters, caption
generation). CI runs it on every push via `.github/workflows/tests.yml`.

It talks directly to the GitHub API using a fine-grained token you paste in
(stored only in your browser). To use it:

1. Create a **fine-grained PAT** (GitHub → Settings → Developer settings →
   Fine-grained tokens) scoped to this repo with **Actions: Read and write** and
   **Contents: Read and write**.
2. Open the dashboard and paste the token under **Connection → Save**.

**Hosting:** GitHub Pages on a **private** repo requires a paid plan. Either make
the repo Public (Settings → General → Change visibility) and enable
Pages (Settings → Pages → Source: **GitHub Actions**) — the included
`pages.yml` workflow then deploys it — **or** simply open `docs/index.html`
in your browser locally; it works identically since it only calls the GitHub API.

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
