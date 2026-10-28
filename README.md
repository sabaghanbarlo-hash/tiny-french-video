# Tiny French - automatic Instagram Stories

*Small steps. Big dreams.* A daily **Story sequence** for [@tiny.french](https://www.instagram.com/tiny.french/): intro, word of the day, a short animated chat between **Adrien and Marinette**, a quiz and the answer. Free: GitHub Actions + Pages, Microsoft Edge neural French voices (edge-tts), Pillow, ffmpeg. This is the French twin of the Tiny Japanese Stories system.

## How it works
1. A **sequence** is one JSON file in `ig-stories/sequences/` (copy `bonjour-01.json`). All text lives there.
2. **Render Stories** (runs automatically when a sequence or the code changes, or by hand) draws 1080x1920 JPEG slides plus an MP4 chat clip with French voices, runs quality checks and saves everything in `ig-stories/out/<id>/` and on the Pages site.
3. Review at `https://<user>.github.io/tiny-french-video/stories.html`.
4. **Approve and schedule Stories** (workflow): enter your name, a start date and a time; every checked sequence gets `approved`, `reviewed_by` and consecutive `publish_at` times. (Or edit those fields in the JSON yourself.)
5. **Publish Stories** (workflow) runs every hour and posts each approved sequence whose `publish_at` has passed, one Story per slide. Run it by hand with `check_only=true` to test the connection (it posts nothing), or with a sequence id (default is a dry run).

Slide types: `intro`, `word`, `convo` (video), `quiz`, `reveal`. Add `"skip": true` to a slide to leave it out. Each sequence ends with a `teaser` for the next word.

## One-time setup
| What | Where |
|---|---|
| Repository secret **`COMPOSIO_API_KEY`** (same key as the other Tiny repos) | Settings -> Secrets and variables -> Actions |
| GitHub Pages source = **GitHub Actions** | Settings -> Pages |
| Optional variables `IG_ACCOUNT`, `IG_EXPECT_USERNAME` | override `ig-stories/config.json` |

## Rules the code enforces
- Posts only to the account named in `ig-stories/config.json` (`expect_username`, `tiny.french`). The Composio login also holds Tiny Japanese; if the connected account is anything else, nothing is posted.
- Never publishes unless `approved` + `reviewed_by` are set and QC has zero errors. A clip with placeholder (test) audio is blocked.
- A slide counts as published only when Instagram returns a media id; progress is saved in `ig-stories/posted.json`, so a retry resumes and never double-posts.
- The French is drawn as live text from the JSON. `french_verified` is always `false`: QC checks consistency (quiz answer = taught meaning, reveal = quiz, example contains the word, audio transcript = subtitles, safe zones, clip length). **A native-speaker review of the French is yours to do** (each sequence lists what is uncertain).

## Instagram API limits
Each slide is its own Story. No stickers (poll, quiz, link), captions or native scheduling, so the quiz uses text options ("reply A, B, C or D"); post the quiz slide by hand if you want the native Quiz sticker. The account must be a professional account.

## Files
`small.py`, `sprites.py` - characters, scenes, voices (shared with tiny-french-story) · `storystudio.py` - renderer + QC · `publish_story.py` - Composio publisher · `schedule_stories.py` - approve/schedule helper · `docs/` - Pages site.

Local test (no voices): `pip install -r requirements.txt` (plus ffmpeg and fonts-dejavu-core), then `python storystudio.py render --sequence bonjour-01 --dummy-audio`.

Reels are made by [tiny-french-story](https://github.com/sabaghanbarlo-hash/tiny-french-story); this repo only does Stories.
