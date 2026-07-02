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
