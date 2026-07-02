# Content campaigns — hands-free posting

Drop images or videos into these folders and they post to Instagram
automatically. No dashboard uploading needed.

## Structure

Each **campaign** is a named folder with its own start date. A **day** is any
folder that contains a `Post`/`Story` (or `posts`/`stories`) subfolder — at any
nesting depth. The naming is flexible and case-insensitive, so all of these
layouts work:

```
content/
  William Collins Ghost 1/           <- a campaign (its own start date)
    Month 1/
      Day 1/
        Post/     -> feed posts on the start date
        Story/    -> stories on the start date
      Day 2/
        Post/
        Story/
  Simple Campaign/                   <- no month layer? also fine
    Day 1/
      posts/
      stories/
  Another Campaign/
    posts/                           <- no day layer? treated as a single day
    stories/
```

- Day folders are ordered **naturally** ("Day 2" before "Day 10", "Month 1"
  before "Month 2") and each gets the **next consecutive date** from the
  campaign's start date: the first day posts on the start date, the next the
  following day, and so on. Ordering is by position, so `Month 2/Day 1`
  continues after `Month 1/Day 20` automatically.
- Set each campaign's **start date** and daily times in the dashboard under
  *Content campaigns* (stored in `data/campaigns.json`).
- Day folders placed directly under `content/` (`content/day1/...`) form a
  default unnamed campaign, for backwards compatibility.
- `Post`/`posts` files become feed posts (videos become Reels).
- `Story`/`stories` files become stories (captions are ignored — Instagram does
  not support them on stories).

## Timing

The first file in a folder goes out at that folder's start time (also set in
the dashboard). Additional files follow automatically at an interval based on
how many files the folder holds: 12 hours divided by the count, kept between
3 and 6 hours. So **2 files post 6h apart, 3 files 4h apart, 4+ files 3h
apart**.

## File formats

- Images: `.jpg`, `.png`, `.webp` — converted to JPEG automatically. Feed
  photos **keep their aspect ratio** when Instagram allows it (between 4:5
  portrait and 1.91:1 landscape), capped at 1080px on the long edge; only
  out-of-range shapes are padded onto a 1080x1080 white square. Stories are
  fitted onto a 1080x1920 white canvas.
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
