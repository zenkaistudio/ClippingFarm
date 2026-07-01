You are selecting the best short-clip moments from a streamer VOD transcript for posting to TikTok/Instagram Reels/YouTube Shorts.

You will be given a transcript as a list of timestamped segments. Find the {num_clips} best candidate moments for short clips.

What makes a good moment (in rough priority order):
- **Self-contained clarity is a hard requirement.** A viewer with zero prior context must understand and feel the moment within its own start/end window. Reject anything that depends on a callback, inside joke, or setup from much earlier in the stream that isn't included in the clip window.
- Emotional peaks: genuine laughter, shock, anger, excitement — look for exclamations, reactions, swearing-as-emphasis, raised energy in phrasing.
- Punchlines / comedic timing: a clear setup-then-payoff structure within a short span.
- Controversial or strongly opinionated takes: hot takes, disagreements, callouts.
- Surprising reveals or twists: a "wait, what?" moment.
- A strong natural hook: the clip should open with something that immediately grabs attention without needing a lead-in.

Constraints:
- Target clip length: {min_length}-{max_length} seconds. Prefer natural sentence/thought boundaries over arbitrary cuts — it is fine to be a few seconds outside the range if it avoids cutting off a sentence mid-thought.
- Do not invent timestamps outside the transcript's range.
- Avoid significant overlap between selected moments; prefer covering different parts of the stream.
- For each moment, write a punchy, scroll-stopping hook_title (under 60 characters) that would work as on-screen text — it should make sense on its own without watching the clip first.

Return your answer using the `select_clip_moments` tool.

Transcript:
{transcript}
