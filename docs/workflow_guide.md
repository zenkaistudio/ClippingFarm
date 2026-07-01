# Clipping Business Workflow Guide

Distilled from research, video transcriptions, and platform experience. This is the operational playbook for running a profitable clipping business using this pipeline.

---

## The Business Model

Brands and streamers pay per-view for short clips of their content posted across TikTok, Instagram Reels, and YouTube Shorts. You create fresh accounts, post clips, and get paid directly — no audience required, no face required.

**Typical rates:**
- Whop Content Rewards: $0.50–$5 per 1,000 views
- Clipify: $1–$5 per 1,000 views
- N3on's network: $40–$50 per 100,000 views
- Kick clipping program: ~$500 per million views
- Adin Ross's top clipper: $60,000 from one streamer's content in a single month

**Where to find campaigns:**
- [Whop Content Rewards](https://whop.com/discover) — search "Content Rewards", 780+ live campaigns
- Clipify Discord / app (verify legitimacy via campaign creator's video description link)
- Specific streamer Discord servers (N3on, Adin Ross, Kai Cenat orbit)

---

## Three-Stage System

### Stage 1 — Setup

1. Create account on campaign platform (Whop recommended — unambiguous, multi-brand)
2. Connect bank account for payouts
3. Connect TikTok and/or Instagram accounts (platform tracks views through your linked accounts)
4. Join a campaign — read the compliance guidelines carefully before making any clips

### Stage 2 — Making Clips

**Hook in first 2 seconds is non-negotiable.** If people don't stop scrolling in the first 2 seconds, the algorithm treats the video as uninteresting.

Two hook strategies:
- **High-energy/controversial moment** — open on the most charged moment in the clip
- **Halo effect** — open on a recognizable face/name to borrow their existing audience pull

**Clip specs:**
- Length: 20–40 seconds sweet spot (min 10s, max ~60s — under 10s tanks watch time even at 100% completion)
- Aspect ratio: 9:16 vertical
- Resolution: 1080p minimum, 4K if available
- Cut dead air every 2–3 seconds — short-form attention spans require constant change

**Caption/title is critical:**
- Every clip needs a title overlay — gives context and can act as the hook
- Must name-drop the recognizable person/IP if one is present
- Controversial or context-setting captions dramatically increase watch time

**Campaign compliance:**
- Always check the specific rules for each campaign (product visibility requirements, mandatory hashtags, length rules, etc.)
- Missing compliance = rejected submission = unpaid, regardless of views
- Some campaigns require posting within 30 minutes of the source upload

**After posting:**
- Paste your post link into the campaign tracker so views are counted
- Check "likes visible" setting — hidden likes = rejection on some platforms

### Stage 3 — Scaling the System

#### Posting cadence (algorithm trust-building)

| Period | Rule | Why |
|--------|------|-----|
| Week 1 | Max 1 post/day, never burst | New accounts that burst-post get shadow-banned or flagged as bots |
| Week 2 | Increase volume, space posts apart through the day | Algorithm trust is building |
| Week 3+ | Post as much as you want (6–8x/day is fine) | Trust established, algorithm knows you're a consistent creator |

Think of each post as a lottery ticket. Posting once a week = 1 ticket. Posting 2x/day = 14 tickets a week. More shots = higher chance of going viral = higher payout. One viral clip can pay $500–$1,000+.

#### Batch production loop

Rather than finding-editing-posting every day (leads to burnout), batch the work:

| Day | Task | Time |
|-----|------|------|
| Day A | Research — browse FYP for viral clips in your niche, save templates | 30 min |
| Day B | Batch raw-cut — download one long-form source, rough-cut 7–15 segments of high-energy moments (no editing yet, just selection) | 60–90 min |
| Day C | Batch finish — add captions, titles, export all clips to a ready folder | 60 min |
| Daily | Open apps, post from ready folder | 3–5 min |

*Day B is what this pipeline automates — the transcribe → detect moments → cut → reframe → caption flow.*

#### Doubling down (best money-maker strategy)

When a clip pops (e.g. 1M views):
1. Take that exact clip
2. Make 3 versions with different titles/caption styles (don't change the video content itself)
3. Post the 3 versions across the next 7 days

This does NOT count as reposting since surface elements changed. You're posting already-proven content. Real result: one 1M-view clip turned into 2.7M cumulative views across 3 variants.

---

## Caption Formula (Viral Template)

The "Tonight/Runway" format consistently drives virality regardless of content.

**Formula:**
```
Tonight, [celebrity/subject] [did something notable] at [prestigious event/location].
[One sentence of additional context that elevates the subject].
[Close with an aspirational or culturally resonant reference — "runway", "history", "legend", etc.]
```

**Why it works:**
- "Tonight" creates live/breaking energy
- Multiple @mentions fire notifications into large fanbases
- Editorial/journalism tone creates pattern interrupt (people expect casual, get "professional")
- Aspirational close leaves positive emotional residue

See [`scripts/prompts/post_description.md`](../scripts/prompts/post_description.md) for niche-specific variants.

---

## Platform-Specific Notes

**TikTok:** Primary platform. Algorithm rewards consistency and early engagement velocity. Never use paid promotion (permanent ban on most campaigns).

**Instagram Reels:** Secondary. Tier 1 audience (US/UK/CA/AU) weighted more heavily by some campaign payout formulas — check your account's audience demographics.

**YouTube Shorts:** Growing. Some campaigns specifically require this platform (especially AI/tech product campaigns).

**Stories:** Views on Stories don't count toward campaign payouts on any platform reviewed. Post to feed/Reels/Shorts only.

---

## Campaign Type Matrix

| Campaign Type | Pipeline fit | Notes |
|--------------|-------------|-------|
| Streamer VODs (gaming, IRL, react) | ✅ Excellent | Full pipeline applies — transcribe, detect moments, cut, caption |
| TV show / movie clips | ✅ Good | Same as streamer — speech-heavy, findable moments |
| Motivational/podcast | ✅ Good | Claude moment-detection tuned for emotional peaks and strong takes |
| AI-generated content (e.g. Higgsfield) | ⚠️ Partial | No transcript to analyze; reframe/caption stages still apply. Check if "no cut" rule applies |
| Music video clips | ❌ Poor fit | No speech; lyrics-based analysis would need a different prompt approach |
| UGC brand campaigns | ❌ Poor fit | Usually requires original creation, not clipping |
