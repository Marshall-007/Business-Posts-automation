# Setup Guide — accounts and credentials

The system publishes through each platform's official API. **None of the
platforms accept a raw username + password from a script** — they all require
API tokens, which you create once from their developer consoles while logged in
to your normal account. This guide lists exactly what to create and which
secret names to store the values under.

Every platform is optional. Configure only the ones you want; the code enables
each platform automatically when its secrets are present.

## Where the credentials go

- **Scheduled posting (recommended):** GitHub repo → **Settings → Secrets and
  variables → Actions → New repository secret**. Create one secret per row in
  the tables below.
- **Local testing:** copy `.env.example` to `.env` and fill in the same names.
  `.env` is git-ignored and never committed.

---

## 1. Anthropic (content generation) — recommended

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | API key from https://platform.claude.com → API Keys |

1. Sign in / sign up at https://platform.claude.com
2. Add a small amount of billing credit (posts are short; cost is cents/month).
3. Create an API key and store it as `ANTHROPIC_API_KEY`.

Without this key the system still works — it rotates through the
`template_posts` list in `config.yaml` instead of writing fresh posts.

---

## 2. Telegram (easiest — good first platform)

| Secret name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your channel/group ID (e.g. `@mychannel` or `-100…`) |

1. In Telegram, message **@BotFather** → `/newbot` → follow the prompts → copy the token.
2. Create your channel (or use an existing one) and add the bot as an **administrator** with permission to post.
3. For a public channel the chat ID is simply `@yourchannelname`.

---

## 3. Facebook Page (cross-posts everything from Instagram)

When these two secrets are set, **every item the scheduler posts to Instagram
is also posted to your Facebook Page** — feed photos as Page photos, Reels as
Page videos, and stories as Page photo/video posts. Facebook is best-effort: if
it ever fails (e.g. an expired token) Instagram still posts and the Facebook
error is recorded on the queue item, never blocking the run.

| Secret name | Value |
|---|---|
| `FACEBOOK_PAGE_ID` | Numeric ID of your Facebook Page |
| `FACEBOOK_PAGE_ACCESS_TOKEN` | Long-lived Page access token |

**a. Create the Gwalava Page** (once, from your personal Facebook account):
go to https://www.facebook.com/pages/create → name it *Gwalava Boards and
Furniture Fittings*, pick a category (e.g. *Furniture shop*), and publish. This
must be done while logged into Facebook as yourself — it cannot be automated.

**b. Create an app:** https://developers.facebook.com → **My Apps → Create
App** (type: **Business**). Under **App settings → Basic**, note the App ID.

**c. Grant permissions & get tokens:** open **Tools → Graph API Explorer**,
select your app, click **Generate Access Token**, and approve
`pages_manage_posts`, `pages_read_engagement`, `pages_show_list`. Then:

- Call `GET /me/accounts` — the response lists your Page's **`id`** (that is
  `FACEBOOK_PAGE_ID`) and a Page **`access_token`**.
- Make it **long-lived**: exchange the token at
  `GET /oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN`,
  then call `GET /me/accounts` again with the long-lived user token — the Page
  token it returns does not expire.

**d. Store** the Page ID and the long-lived Page access token as the two
secrets above (GitHub → Settings → Secrets and variables → Actions).

You can paste the Page ID and Page token to me and I will confirm they work by
running a live cross-post test on GitHub Actions.

## 4. Instagram (Instagram Login flow — posts require an image)

| Secret name | Value |
|---|---|
| `INSTAGRAM_ACCESS_TOKEN` | Access token starting with `IGAA…` |
| `INSTAGRAM_USER_ID` | Your Instagram account ID (from `GET https://graph.instagram.com/me`) |

1. Your account must be a **Business** or **Creator** account (Instagram app → Settings → Account type and tools → Switch to professional account).
2. Create an app at https://developers.facebook.com with the **Instagram** product, add the **Instagram Business Login** use case, and grant `instagram_business_basic` + `instagram_business_content_publish`.
3. Generate a user token and confirm it works:
   `https://graph.instagram.com/me?fields=id,username&access_token=IGAA…`
   The `id` it returns is your `INSTAGRAM_USER_ID`.
4. For scheduled posting you need a **long-lived** token (60 days). The
   `Refresh Instagram token` workflow keeps it alive automatically and writes the
   renewed token back to the secret. To enable it, add two more secrets:

   | Secret name | Value |
   |---|---|
   | `INSTAGRAM_APP_SECRET` | Your Meta app's client secret (App settings → Basic). Needed once to upgrade a short-lived token to 60 days. |
   | `GH_PAT` | A fine-grained PAT scoped to this repo with **Secrets: Read and write** (so the workflow can save the refreshed token). |

   Then run **Actions → Refresh Instagram token → Run workflow** once. From then on
   it refreshes weekly on its own and you never touch the token again.
5. Instagram requires an image for every post — add public image URLs to `image_urls` in `config.yaml`; the system rotates through them.

## 5. LinkedIn

| Secret name | Value |
|---|---|
| `LINKEDIN_ACCESS_TOKEN` | OAuth token with `w_member_social` (or `w_organization_social`) |
| `LINKEDIN_AUTHOR_URN` | `urn:li:person:XXXX` or `urn:li:organization:XXXX` |

1. Create an app at https://www.linkedin.com/developers → request access to **"Share on LinkedIn"** (and **"Community Management API"** for company pages).
2. Generate an access token via the OAuth flow (the developer portal has a token generator under *Auth*).
3. Personal profile: your URN is `urn:li:person:{id}` where `{id}` comes from `GET https://api.linkedin.com/v2/userinfo` (`sub` field). Company page: `urn:li:organization:{numeric id from the page URL}`.

## 6. X (Twitter)

| Secret name | Value |
|---|---|
| `TWITTER_API_KEY` | App "API Key" (consumer key) |
| `TWITTER_API_SECRET` | App "API Secret" |
| `TWITTER_ACCESS_TOKEN` | Your account's access token |
| `TWITTER_ACCESS_TOKEN_SECRET` | Your account's access token secret |

1. Sign in at https://developer.x.com → create a project + app (the **Free** tier allows posting).
2. In the app settings, set **App permissions** to *Read and write*.
3. Under **Keys and tokens**, generate all four values above (regenerate the access token *after* switching to read-write).

---

## Final checklist

- [ ] Secrets added in GitHub → Settings → Secrets and variables → Actions
- [ ] `config.yaml` updated with your business profile and topics
- [ ] (Instagram only) public image URLs added to `image_urls` in `config.yaml`
- [ ] Test run: Actions tab → **Publish business posts** → *Run workflow*

> **Security note:** never share account passwords with anyone (including in
> chat). Only the API tokens above are needed, and they should live only in
> GitHub Secrets or your local `.env`.
