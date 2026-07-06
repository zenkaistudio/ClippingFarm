import json
import os
from datetime import datetime, timedelta, timezone
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


def schedule_to_buffer(public_url: str, caption: str, channel_id: str,
                        buffer_token: str, minutes_from_now: int = 15) -> dict:
    scheduled_at = (
        datetime.now(timezone.utc) + timedelta(minutes=minutes_from_now)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    query = """
    mutation CreatePost($input: PostCreateInput!) {
        postCreate(input: $input) {
            post { id status scheduledAt }
            errors { message }
        }
    }
    """
    variables = {
        "input": {
            "channelId": channel_id,
            "content": {
                "text": caption,
                "media": {"url": public_url},
            },
            "scheduledAt": scheduled_at,
        }
    }
    resp = requests.post(
        "https://api.buffer.com/graphql",
        headers={
            "Authorization": f"Bearer {buffer_token}",
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def run(clip_path: Path, hook_title: str, category: str,
        channel_ids: list[str], buffer_token: str, claude_model: str,
        minutes_from_now: int = 15) -> dict:
    cloudinary_url = upload_to_cloudinary(clip_path)
    caption = generate_caption(hook_title, category, claude_model)

    buffer_results = []
    for channel_id in channel_ids:
        result = schedule_to_buffer(
            cloudinary_url, caption, channel_id, buffer_token, minutes_from_now
        )
        buffer_results.append({"channel_id": channel_id, "result": result})

    return {
        "cloudinary_url": cloudinary_url,
        "caption": caption,
        "buffer_results": buffer_results,
    }
