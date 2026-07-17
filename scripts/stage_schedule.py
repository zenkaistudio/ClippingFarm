import os
from pathlib import Path

import cloudinary
import cloudinary.uploader
import requests
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _configure_cloudinary() -> None:
    cloudinary.config(
        cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
        api_key=os.environ["CLOUDINARY_API_KEY"],
        api_secret=os.environ["CLOUDINARY_API_SECRET"],
        secure=True,
    )


def upload_to_cloudinary(video_path: Path) -> str:
    _configure_cloudinary()
    result = cloudinary.uploader.upload_large(
        str(video_path),
        resource_type="video",
        folder="clippingfarm",
        use_filename=True,
        unique_filename=True,
    )
    return result["secure_url"]


def generate_caption(hook_title: str, category: str, claude_model: str) -> str:
    client = Anthropic()
    prompt = f"""Write a viral TikTok caption using the Tonight/Runway formula.

Hook title: {hook_title}
Clip category: {category}

Formula: "Tonight, [subject] [did something notable]. [One sentence of elevating context]. [Aspirational close — one powerful word or phrase like 'history', 'legend', 'the moment', etc.]"

Rules:
- Under 200 characters total
- Include 3 relevant hashtags at the end
- No emojis
- Journalistic/editorial tone — reads like entertainment news
- Return only the caption, nothing else"""

    msg = client.messages.create(
        model=claude_model,
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


# Confirmed 2026-07-08 via live GraphQL introspection against api.buffer.com/graphql
# (scripts/buffer_introspect.py) - the mutation is `createPost`/`CreatePostInput`, NOT
# `postCreate`/`PostCreateInput` (that mutation does not exist on Buffer's real schema).
_CREATE_POST_MUTATION = """
mutation CreatePost($input: CreatePostInput!) {
    createPost(input: $input) {
        ... on PostActionSuccess { post { id status dueAt } }
        ... on InvalidInputError { message }
        ... on UnauthorizedError { message }
        ... on LimitReachedError { message }
        ... on RestProxyError { message }
        ... on UnexpectedError { message }
        ... on NotFoundError { message }
    }
}
"""

# Per-platform `metadata` block required/supported by Buffer's schema (confirmed via
# introspection of PostInputMetaData / InstagramPostMetadataInput / TikTokPostMetadataInput /
# YoutubePostMetadataInput). Instagram *requires* `type` + `shouldShareToFeed`; omitting
# them causes a hard rejection. TikTok/YouTube fields are optional but worth setting.
def _platform_metadata(platform: str, caption: str) -> dict:
    if platform == "instagram_reels":
        return {"instagram": {"type": "reel", "shouldShareToFeed": True}}
    if platform == "tiktok":
        return {"tiktok": {"title": caption[:150]}}
    if platform == "youtube_shorts":
        return {"youtube": {"title": caption[:100], "privacy": "public", "madeForKids": False}}
    raise ValueError(f"Unknown platform: {platform}")


def schedule_to_buffer(public_url: str, caption: str, channel_id: str, platform: str,
                        buffer_token: str, scheduled_at: str | None = None) -> dict:
    """Create a Buffer post for a video clip.

    scheduled_at=None -> added to the channel's Buffer queue (safest default).
    scheduled_at="YYYY-MM-DDTHH:MM:SSZ" -> scheduled for that exact time.
    """
    variables = {
        "input": {
            "channelId": channel_id,
            "schedulingType": "automatic",
            "mode": "addToQueue" if scheduled_at is None else "customScheduled",
            "text": caption,
            "assets": [{"video": {"url": public_url}}],
            "metadata": _platform_metadata(platform, caption),
            **({"dueAt": scheduled_at} if scheduled_at else {}),
        }
    }
    resp = requests.post(
        "https://api.buffer.com/graphql",
        headers={
            "Authorization": f"Bearer {buffer_token}",
            "Content-Type": "application/json",
        },
        json={"query": _CREATE_POST_MUTATION, "variables": variables},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(f"Buffer GraphQL error for channel {channel_id}: {data['errors']}")
    result = data["data"]["createPost"]
    if "message" in result:
        raise RuntimeError(f"Buffer rejected post for channel {channel_id} ({platform}): {result['message']}")
    return result["post"]


def run(clip_path: Path, hook_title: str, category: str,
        platform_channel_ids: dict[str, str], buffer_token: str,
        scheduled_at: str | None = None) -> dict:
    """Ship one clip to Buffer for each platform in platform_channel_ids.

    Uses the clip's hook_title directly as the caption - no AI caption generation.
    """
    cloudinary_url = upload_to_cloudinary(clip_path)
    caption = hook_title

    buffer_results = []
    for platform, channel_id in platform_channel_ids.items():
        try:
            post = schedule_to_buffer(
                cloudinary_url, caption, channel_id, platform, buffer_token, scheduled_at
            )
            buffer_results.append({"platform": platform, "channel_id": channel_id, "post": post})
        except Exception as exc:
            buffer_results.append({"platform": platform, "channel_id": channel_id, "error": str(exc)})

    return {
        "cloudinary_url": cloudinary_url,
        "caption": caption,
        "buffer_results": buffer_results,
    }
