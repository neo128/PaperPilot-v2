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

# Full flow: create + upload
for attempt in range(5):
    try:
        if attempt > 0:
            wait = attempt * 15
            print(f"Retry {attempt+1}, waiting {wait}s...")
            time.sleep(wait)
        
        # Step 1: Create attachment
        print(f"Creating attachment...")
        resp = requests.post(
            f"https://api.zotero.org/users/{user_id}/items",
            headers=headers,
            json=[attachment_meta],
            timeout=30,
        )
        if resp.status_code == 429:
            print("Rate limited...")
            continue
        print(f"POST status: {resp.status_code}")
        resp.raise_for_status()
        result = resp.json()
        success = result.get("success", {})
        if not success:
            print(f"No success in response: {json.dumps(result, indent=2)[:300]}")
            continue
        attachment_key = list(success.values())[0]
        print(f"Attachment key: {attachment_key}")
        time.sleep(10)

        # Step 2: Get upload URL
        print(f"Getting upload URL...")
        upload_auth_url = f"https://api.zotero.org/users/{user_id}/items/{attachment_key}/file"
        resp2 = requests.get(upload_auth_url, headers=headers, timeout=30)
        if resp2.status_code == 429:
            print("Rate limited on upload auth...")
            continue
        print(f"GET auth status: {resp2.status_code}")
        if resp2.status_code == 404:
            print("Attachment not yet available, retrying...")
            time.sleep(15)
            continue
        resp2.raise_for_status()
        auth_info = resp2.json()
        upload_url = auth_info.get("url", "")
        print(f"Upload URL: {upload_url[:100]}")
        if not upload_url:
            print("No upload URL, response:")
            print(json.dumps(auth_info, indent=2)[:500])
            break

        # Step 3: Upload file
        print(f"Uploading file...")
        resp3 = requests.put(
            upload_url,
            data=file_content,
            headers={"Content-Type": "text/markdown"},
            timeout=60,
        )
        if resp3.status_code == 429:
            print("Rate limited on upload...")
            continue
        print(f"PUT status: {resp3.status_code}")
        resp3.raise_for_status()
        print(f"File uploaded successfully!")
        print(f"Done: 论文解读2026-04-13.md attached to paper NJQ4H5S5 (attachment: {attachment_key})")
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
