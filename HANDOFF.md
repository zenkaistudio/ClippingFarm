# Clipping Handoff (Mac to Windows desktop, Nov 18 2026)

Claude on the desktop: read this whole file before doing any clipping work for Mal.

## House rules

- Call the user Mal.
- No em dashes or stylistic slashes in anything you write for Mal.
- Never delete downloaded media unless Mal asks.
- Clips are 9:16 vertical (1080x1920). Still confirm the aspect ratio with Mal before any new render type.
- When Mal posts, they add their own titles. Farm clips go out with **Title overlay OFF** and **Captions OFF**, so only the farm edit and the @DogenVaultz watermark remain.

## 1. Finding viral moments (the scout workflow)

Mal's rules:
- Never use chat spikes. Kai's chat is always busy, so spikes mean nothing.
- Never download a full stream. It won't fit on disk and it's slow.

Steps:
1. **Most Replayed heatmap** is the best signal. It only exists after a stream ends.
   - venv\Scripts\python scripts\scout_heatmap.py URL --top 15
   - Narrow to a section with: --after 9:00:00 --before 9:30:00
2. **Transcript** works on live streams too. Pull audio only for the section, about 30 minutes at a time. Mal prefers after the 9 hour mark.
   - venv\Scripts\python scripts\grab_range.py URL 9:00:00 9:30:00 "kai scout" --audio-only
   - venv\Scripts\python scripts\scout_transcript.py "yt downloads\scout\kai scout 9h00m00-9h30m00.m4a" 9:00:00
   - Lines are printed with real stream timestamps.
   - A * marks shouting or keyword lines.
   - What to look for: Kai dying on a mission, fights, cops, big screaming reactions, story twists he rants about.
3. **Confirm what's on screen** before ranking. The transcript only covers what Kai says, not what happens in the game. Grab a short video range of the candidate and pull frames:
   - tools\ffmpeg\bin\ffmpeg.exe -i clip.mp4 -vf "fps=1/5,scale=320:-1,tile=6x6" sheet.png
4. **Post a ranked list in chat.** For each pick give:
   - the stream timestamp range
   - what happens
   - the best quote

   Mal picks. Download **only** the picks.

## 2. Finding stream timestamps

- Stream time = seconds since the stream started. It is the same as the YouTube player timestamp on the VOD or on a live DVR.
- In a live stream's DASH feed, each segment is 5 seconds, so segment number sq = stream seconds / 5.
- The response header X-Head-Seqnum gives the live edge, which tells you how long the stream has run.
- To find a scene Mal describes, transcribe the section with the steps above, then contact sheet the candidate area to confirm.

## 3. Downloading only the picked ranges (1080p60 mp4)

One command, on both Mac and Windows:

venv\Scripts\python scripts\grab_range.py URL START END "short name"

Example:

venv\Scripts\python scripts\grab_range.py https://www.youtube.com/watch?v=H-4PyJlhI9g 46:35 48:23 "kai GTA6 Lucia kisses Cal"

- Output: yt downloads\<name> <start>-<end>.mp4, as h264 1080p60 with aac.
- **Still live:** `yt-dlp --download-sections` fails on live DASH, so the script fetches the 5 s segments directly.
  - It uses itag 299 for video and 140 for audio, then muxes with ffmpeg -c copy.
  - Times snap to the 5 s grid.
- **Ended:** the script hands off to yt-dlp --download-sections with the same formats.
- **Error that a segment failed:** the signed URL expired. Just rerun the command.
- **Setup:** yt-dlp is now in requirements.txt. On the desktop, run once:
  - venv\Scripts\pip install -U -r requirements.txt
  - If yt-dlp ever stops working, `pip install -U yt-dlp` is the usual fix.

## 4. Kai GTA 6 streams and clips from today

**Streams:**
- **Old stream** https://www.youtube.com/watch?v=VZqAPdUvqnQ (live Nov 18, 8:00 AM EST)
  - It has gone **PRIVATE**. Nothing more can be downloaded from it.
- **New stream** https://www.youtube.com/watch?v=H-4PyJlhI9g, "PLAYING GTA 6 FOR THE FIRST TIME" (live Nov 18, 7:47 PM EST)
  - Still live at last check.
  - Kai privates streams after they end, so grab picks while it's up.
- Find new streams at youtube.com/@KaiCenatLive/streams, not @KaiCenat.

**Old stream timestamps (private now, clips already downloaded):**
- 8:35:40 to 8:37:51: Lucia walking through the apartment rooms. This is the clip Mal posted.
- 9:18:25 to 9:20:30: Kai loses the fish. Already exported.
- **Skunk Ape mission:**
  - 9:48:00 highway ride
  - 9:51:40 mission start (red hoodie figure: "I'm checkin' your EMF... Skunk ape")
  - 9:54:00 flashlight search
  - 9:58:45 "Return to the truck"
  - Downloaded range: 9:51:30 to 9:59:00
  - Not run through the farm yet. The end point is still Mal's call.

**New stream timestamps:**
- 46:38 Cal (bucket hat, green fish shirt) helps Jason off the boat
- 47:31 Lucia kisses Cal
- 47:43 to 48:22 Kai pauses and rants ("bleeding out my stomach and you wanna kiss my man")
- Downloaded range: 46:35 to 48:23

**Finished clip (Mac, clipping/output):**
- kai_gta6_lucia_kisses_cal_full_9baf54__clip01__lucia_kisses_cal_and_kai_crashes_out.mp4
- 1:48, full scene, no title, no captions

## 5. Running clips through the Clipping Farm

- Start it with **Start Clipping Farm.bat**. It opens at http://127.0.0.1:5050.
- Upload the clip and set:
  - **Title overlay unchecked**
  - **Captions unchecked** (new toggle, added today)
- Pipeline stages: transcribe, detect moments (Claude), cut, reframe (face tracking), captions burn.
- With both toggles off, the captions burn adds only the watermark.
- **The farm splits a scene into its own short picks.** For a scene Mal wants whole, like the kiss clip, run it as one candidate from the command line:
  1. Upload the clip, or put it in uploads\.
  2. Write work\<video_id>\candidates.json as one entry:
     - [{"start":0.0,"end":<duration>,"hook_title":"<title>"}]
     - For anything else the stage expects, copy the fields from any farm candidates.json.
  3. Run these in order. Each command starts with: venv\Scripts\python scripts\run_pipeline.py --input "uploads\<file>.mp4"
     - first: --stage transcribe
     - then: --stage cut
     - then: --stage reframe
     - last: --stage captions --no-title --no-captions
  4. The result lands in output\.
- **Upload API:** POST /api/upload with these fields:
  - video
  - num_clips
  - preset_id
  - title_enabled=false
  - captions_enabled=false
  - With curl, send the text fields with --form-string.

## 6. Windows notes

- ffmpeg: the farm uses tools\ffmpeg\bin\ffmpeg.exe (git ignored). It should already be on the desktop.
  - If it's missing, put a full Windows build there. It needs libass and libx264.
  - The Mac uses its own static build in tools/ffmpeg-mac, which is not in git and not needed on Windows.
- Transcription uses faster-whisper on Windows, on CUDA if available, otherwise CPU. The model is set by whisper_model in config.json ("medium").
- Run scripts from the clipping folder with venv\Scripts\python.

## 7. YouTube posting notes from today

- Put keywords in the Studio **Tags** box: single words, no punctuation, 500 character limit.
- Don't put keyword lists in the description. YouTube treats that as spam.
- Description: 2 short sentences plus 3 to 5 hashtags. More than 60 hashtags means YouTube ignores all of them.
