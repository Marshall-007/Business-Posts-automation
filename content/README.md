# Content folders — hands-free posting

Drop images or videos into these folders and they post to Instagram
automatically. No dashboard uploading needed.

## Structure

```
content/
  day1/
    posts/      -> feed posts   (day 1 of the campaign)
    stories/    -> stories      (day 1)
  day2/
    posts/
    stories/
  ...
```

- **day1** posts on the campaign **start date** (set in the dashboard under
  *Content folders*, stored in `data/campaign.json`). day2 is the next day,
  day3 the day after, and so on.
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
