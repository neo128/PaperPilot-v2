#!/usr/bin/env python3
"""Upload the paper analysis as an attachment to the Zotero item."""
import time
import requests
import json

from paperpilot.utils.env import load_dotenv_if_present
load_dotenv_if_present()

from paperpilot.utils.config import load_app_settings

settings = load_app_settings()
user_id = settings.zotero.user_id
api_key = settings.zotero.api_key

paper_key = "NJQ4H5S5"
file_path = "/home/user/.openclaw/workspace/agents/paper/code/PaperPilot-v2/论文解读2026-04-13.md"

with open(file_path, "rb") as f:
    file_content = f.read()

print(f"File size: {len(file_content)} bytes")

headers = {
    "Zotero-API-Key": api_key,
    "Content-Type": "application/json",
}

attachment_meta = {
    "itemType": "attachment",
    "parentItem": paper_key,
    "linkMode": "imported_file",
    "title": "论文解读2026-04-13.md",
    "contentType": "text/markdown",
    "filename": "论文解读2026-04-13.md",
}

# Wait first to avoid rate limiting
print("Waiting 30s before starting to avoid rate limiting...")
time.sleep(30)

for attempt in range(5):
    try:
        if attempt > 0:
            wait = attempt * 15
            print(f"Retry attempt {attempt+1}, waiting {wait}s...")
            time.sleep(wait)
        
        # Step 1: Create attachment metadata
        print(f"Creating attachment metadata...")
        resp = requests.post(
            f"https://api.zotero.org/users/{user_id}/items",
            headers=headers,
            json=[attachment_meta],
            timeout=30,
        )
        print(f"POST status: {resp.status_code}")
        if resp.status_code == 429:
            continue
        resp.raise_for_status()
        result = resp.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        attachment_key = result[0].get("key", "")
        if not attachment_key:
            print("No key returned, trying again...")
            continue
        print(f"Attachment created. Key: {attachment_key}")
        time.sleep(5)

        # Step 2: Upload file content
        print(f"Uploading file...")
        upload_url = f"https://api.zotero.org/users/{user_id}/items/{attachment_key}/file"
        upload_headers = {
            "Zotero-API-Key": api_key,
            "Content-Type": "text/markdown",
        }
        resp2 = requests.put(
            upload_url,
            headers=upload_headers,
            data=file_content,
            timeout=60,
        )
        print(f"PUT status: {resp2.status_code}")
        if resp2.status_code == 429:
            continue
        resp2.raise_for_status()
        print(f"File uploaded! Status: {resp2.status_code}")
        print(f"Done: 论文解读2026-04-13.md attached to paper NJQ4H5S5")
        break

    except requests.exceptions.HTTPError as e:
        if "429" in str(e):
            print("Rate limited, retrying...")
            continue
        else:
            print(f"HTTP Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text[:500]}")
            break
    except Exception as e:
        print(f"Failed: {type(e).__name__}: {e}")
        break
