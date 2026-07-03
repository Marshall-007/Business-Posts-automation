# User Manual

How to run the posting system day to day, in plain language. The same manual
lives inside the dashboard under **User Manual**; connecting accounts and
credentials is covered by **Setup Instructions** (and SETUP.md).

## What this system does

It posts your marketing photos to **Instagram and Facebook** automatically -
feed posts and stories - one month of content at a time. You load a month of
photos once, pick a start date, tick the month, and it posts every day by
itself: captions are written automatically with your phone number, website and
hashtags, and every post is mirrored to Facebook (stories land in the Page's
Stories ring). A robot on GitHub wakes up every 15 minutes and does the work;
the dashboard is your remote control.

## Getting around the dashboard

| Section | What it is for |
|---|---|
| Dashboard | Today's numbers, the activity log (every post + any errors), latest runs |
| Scheduled Posts | Everything waiting to publish, with dates and cancel buttons |
| Auto Posts | Your campaigns and months - load content and switch months on here |
| Companies | Switch between the businesses you manage; run their guided setup |
| Admin | Add a brand-new company (its repository is created automatically) |
| User Manual / Setup Instructions | This guide, and the credentials guide |
| Settings | The GitHub connection for the active company |

The left menu's **Active company** chip always shows which business you are
working on.

## Post a month of content (the everyday job)

1. Open **Auto Posts**.
2. Scroll to **Bulk upload and auto-sort**. Pick the campaign (or type a new
   name) and keep the suggested month (e.g. `Month 2`).
3. Choose your **feed images** (polished ones for the grid) and **story
   images** (casual ones). Pick 2 or 3 per day for each.
4. Press **Preview plan** to see the day split, then **Sort and upload**.
5. Find the new month card above. Set its **start date**, tick **Instagram**
   and **Facebook**, tick the **month's checkbox**, press **Save campaign**.
6. Done. Day 1 posts on the start date, day 2 the next day, and so on. Open
   the **Day-by-day plan** inside the month card to see exactly what posts when.

**Timing:** feed posts start at the campaign's "Posts time", stories at the
"Stories time". A day with 2 files posts them 6 hours apart; 3 files, 4 hours
apart.

## Pause, resume, or fix a mistake

- **Pause a month:** untick its checkbox and Save. Cancel any already-queued
  posts under Scheduled Posts.
- **Cancel one post:** Scheduled Posts -> Cancel on the row (removes the photo too).
- **Wrong start date before anything posted:** change the date and Save.
  Queued posts keep their old time - cancel them and they re-queue.
- **Post something right now:** Scheduled Posts -> "Process due posts now",
  or Dashboard -> "Post now" for a one-off standard post.

## Reading the activity log

Dashboard -> **Activity log**. One row per attempt: when, platform, feed or
story, result. Green **posted** shows the platform's post id; red **failed**
shows the platform's own error message (it usually says exactly what is wrong,
e.g. an expired token). Failed posts retry automatically up to three times.

## Add a new company (about 30 minutes end to end)

1. **Admin**: business name, what it does, phone, website -> **Add Company**.
   The repository is created automatically on `main`, captions personalized,
   starter data cleared.
2. **Companies**: press **Guided setup** on the new card. The wizard walks
   through the GitHub token, Facebook Page, Instagram and GitHub Pages,
   verifying each step; all tokens are made long-lived or permanent.
3. **Auto Posts**: bulk-upload their first month, set date + platforms, tick,
   Save.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Nothing is posting | Month ticked with a start date today or later? Items pending in Scheduled Posts? Red rows in the activity log? |
| Token error in the log | Re-run Guided setup from that platform's step with a fresh token |
| Facebook stories "missing" | Page stories show in the Facebook mobile app's Stories ring and expire after 24h; the activity log's post id proves publication |
| "No access token set" | Settings -> paste the company's GitHub token and Save, or switch companies |
| Upload seems stuck | Large batches take a minute; watch the status line, reload and retry on error |
| Fewer posts than expected today | The safety cap allows 20 posts per rolling 24h; the rest follow automatically |

## Rules the system enforces for you

- Photos are converted and resized automatically (stories 1080x1920).
- Each photo is deleted from storage after it posts.
- Captions never repeat back to back, always carry your contact line, and stay
  within Instagram's limits.
- A month with long-past dates will not flood out old posts.
- Instagram tokens renew weekly by themselves; permanent Facebook Page tokens
  never expire.
