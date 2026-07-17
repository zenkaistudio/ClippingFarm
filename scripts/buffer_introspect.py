"""One-off diagnostic: confirm Buffer's real GraphQL schema before trusting any
hand-written mutation. Read-only (introspection + channel list) - creates no posts.
"""

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BUFFER_TOKEN = os.environ.get("BUFFER_ACCESS_TOKEN", "")
ENDPOINT = "https://api.buffer.com/graphql"

INTROSPECTION_QUERY = """
{
  __schema {
    mutationType { fields { name } }
    queryType { fields { name } }
  }
}
"""

CREATE_POST_INPUT_QUERY = """
{
  __type(name: "CreatePostInput") {
    name
    inputFields { name type { name kind ofType { name kind } } }
  }
}
"""

ASSET_INPUT_QUERY = """
{
  __type(name: "AssetInput") {
    name
    inputFields { name type { name kind ofType { name kind } } }
  }
}
"""

CHANNELS_QUERY = """
{
  channels {
    id
    service
    serviceUsername
  }
}
"""


def _post(query: str, variables: dict | None = None) -> dict:
    resp = requests.post(
        ENDPOINT,
        headers={"Authorization": f"Bearer {BUFFER_TOKEN}", "Content-Type": "application/json"},
        json={"query": query, **({"variables": variables} if variables else {})},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    print("=== Mutations / Queries available ===")
    schema = _post(INTROSPECTION_QUERY)
    print(json.dumps(schema, indent=2))

    print("\n=== CreatePostInput fields ===")
    try:
        print(json.dumps(_post(CREATE_POST_INPUT_QUERY), indent=2))
    except Exception as exc:
        print(f"failed: {exc}")

    print("\n=== AssetInput fields ===")
    try:
        print(json.dumps(_post(ASSET_INPUT_QUERY), indent=2))
    except Exception as exc:
        print(f"failed: {exc}")

    print("\n=== Channels ===")
    try:
        print(json.dumps(_post(CHANNELS_QUERY), indent=2))
    except Exception as exc:
        print(f"failed: {exc}")
