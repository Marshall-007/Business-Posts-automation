# Content campaigns — hands-free posting

Drop images or videos into these folders and they post to Instagram
automatically. No dashboard uploading needed.

## Structure

Each **campaign** is a named folder with its own start date. Add as many as you
like:

```
content/
  William Collins Ghost 1/     <- a campaign (its own start date)
    day1/
      posts/      -> feed posts on the start date
      stories/    -> stories on the start date
    day2/
      posts/
      stories/
  Another Campaign/            <- add more campaigns any time
    day1/
      ...
```

- Set each campaign's **start date** and daily times in the dashboard under
  *Content campaigns* (stored in `data/campaigns.json`). day1 posts on that
  campaign's start date, day2 the next day, and so on.
- A campaign with no dayN folders but `posts/`/`stories/` directly is treated
  as day1.
- Day folders placed directly under `content/` (`content/day1/...`) form a
  default unnamed campaign, for backwards compatibility.
- **posts/** files become feed posts (videos become Reels).
- **stories/** files become stories (captions are ignored — Instagram does not
  support them on stories).

## Timing

The first file in a folder goes out at that folder's start time (also set in
the dashboard). Additional files follow automatically at an interval based on
how many files the folder holds: 12 hours divided by the count, kept between
3 and 6 hours. So **2 files post 6h apart, 3 files 4h apart, 4+ files 3h
apart**.

## File formats

- Images: `.jpg`, `.png`, `.webp` — anything that is not already a correctly
  sized JPEG is converted automatically (feed 1080x1080, story 1080x1920,
  padded onto white).
- Videos: `.mp4`, `.mov` (keep them under ~40 MB).

## Captions (feed posts only)

Checked in this order:

1. A text file with the same name as the image: `photo1.jpg` -> `photo1.txt`
2. A `caption.txt` shared by the whole folder
3. Otherwise a caption is generated from the business profile in `config.yaml`

## Lifecycle

Every 15 minutes the scheduler converts new images, queues them with their
times (visible in the dashboard Queue, where individual items can be
cancelled), posts whatever is due, and **deletes each file after it posts**.
Nothing happens until the campaign is **enabled** in the dashboard.
