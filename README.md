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
