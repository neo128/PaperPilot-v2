#!/usr/bin/env python3
"""Add the paper analysis as a Zotero note attachment."""
import time
import requests

from paperpilot.utils.env import load_dotenv_if_present
load_dotenv_if_present()

from paperpilot.utils.config import load_app_settings

settings = load_app_settings()
user_id = settings.zotero.user_id
api_key = settings.zotero.api_key
paper_key = "NJQ4H5S5"

file_path = "/home/user/.openclaw/workspace/agents/paper/code/PaperPilot-v2/论文解读2026-04-13.md"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Convert markdown to HTML for Zotero note
html = f'<div data-schema-version="9"><h1>论文解读</h1>{content.replace(chr(10), "<br>")}</div>'

note = {
    "itemType": "note",
    "parentItem": paper_key,
    "note": html,
    "tags": [{"tag": "AI解读"}],
}

headers = {
    "Zotero-API-Key": api_key,
    "Content-Type": "application/json",
}

for attempt in range(5):
    try:
        if attempt > 0:
            wait = attempt * 15
            print(f"Retry {attempt+1}, waiting {wait}s...")
            time.sleep(wait)
        
        print(f"Creating note attachment...")
        resp = requests.post(
            f"https://api.zotero.org/users/{user_id}/items",
            headers=headers,
            json=[note],
            timeout=30,
        )
        
        if resp.status_code == 429:
            print("Rate limited...")
            continue
        
        resp.raise_for_status()
        result = resp.json()
        success = result.get("success", {})
        if success:
            note_key = list(success.values())[0]
            print(f"Note created successfully!")
            print(f"Note key: {note_key}")
            print(f"Content length: {len(content)} chars")
            print(f"Done: 论文解读2026-04-13 已添加为 Zotero Note 到论文 NJQ4H5S5")
        else:
            print(f"Failed: {result}")
        break

    except requests.exceptions.HTTPError as e:
        if "429" in str(e):
            print("Rate limited, retrying...")
            continue
        else:
            print(f"HTTP Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text[:300]}")
            break
    except Exception as e:
        print(f"Failed: {type(e).__name__}: {e}")
        break
