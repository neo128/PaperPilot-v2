#!/usr/bin/env python3
"""Import the SAE VLA paper into Zotero with retry logic."""
import time
import requests

from paperpilot.utils.env import load_dotenv_if_present
load_dotenv_if_present()

from paperpilot.clients.zotero import ZoteroClient
from paperpilot.utils.config import load_app_settings

settings = load_app_settings()
zotero = ZoteroClient(settings.zotero.user_id, settings.zotero.api_key)

# Wait to avoid rate limiting
time.sleep(5)

# Check if paper exists via a targeted search
exists = False
for attempt in range(3):
    try:
        items = list(zotero.iter_items(limit=50))
        for item in items:
            data = item.get("data", {})
            archive_loc = data.get("archiveLocation", "")
            url = data.get("url", "")
            if "2603.19183" in archive_loc or "2603.19183" in url:
                exists = True
                print(f"Already in Zotero: {data.get('title', 'Untitled')}")
                break
        break
    except Exception as e:
        wait = (attempt + 1) * 10
        print(f"Check attempt {attempt+1} failed ({e}), retrying in {wait}s...")
        time.sleep(wait)

time.sleep(3)

if not exists:
    paper = {
        "title": "Sparse Autoencoders Reveal Interpretable and Steerable Features in VLA Models",
        "authors": [
            {"name": "Aiden Swann"},
            {"name": "Lachlain McGranahan"},
            {"name": "Hugo Buurmeijer"},
            {"name": "Monroe Kennedy III"},
            {"name": "Mac Schwager"},
        ],
        "abstract": "Vision-Language-Action (VLA) models have emerged as a promising approach for general-purpose robot manipulation. However, their generalization is inconsistent: while these models can perform impressively in some settings, fine-tuned variants often fail on novel objects, scenes, and instructions. We apply mechanistic interpretability techniques to better understand the inner workings of VLA models. To probe internal representations, we train Sparse Autoencoders (SAEs) on hidden layer activations of the VLA. SAEs learn a sparse dictionary whose features act as a compact, interpretable basis for the model's computation. We find that the large majority of extracted SAE features correspond to memorized sequences from specific training demonstrations. However, some features correspond to interpretable, general, and steerable motion primitives and semantic properties, offering a promising glimpse toward VLA generalizability. We propose a metric to categorize features according to whether they represent generalizable transferable primitives or episode-specific memorization. We validate these findings through steering experiments on the LIBERO benchmark. We show that individual SAE features causally influence robot behavior. Steering general features induces behaviors consistent with their semantic meaning and can be applied across tasks and scenes. This work provides the first mechanistic evidence that VLAs can learn generalizable features across tasks and scenes. We observe that supervised fine-tuning on small robotics datasets disproportionately amplifies memorization. In contrast, training on larger, more diverse datasets (e.g., DROID) or using knowledge insulation promotes more general features. We provide an open-source codebase and user-friendly interface for activation collection, SAE training, and feature steering.",
        "src_url": "https://arxiv.org/pdf/2603.19183",
        "arxiv_id": "2603.19183",
        "published": "2026-03-19",
    }

    payload = {
        "itemType": "journalArticle",
        "title": paper["title"],
        "creators": [{"creatorType": "author", "name": a["name"]} for a in paper["authors"]],
        "abstractNote": paper["abstract"],
        "url": "https://arxiv.org/abs/2603.19183",
        "date": paper["published"],
        "archive": "arXiv",
        "archiveLocation": paper["arxiv_id"],
        "tags": [
            {"tag": "PaperPilot-v2"},
            {"tag": "VLA"},
            {"tag": "Mechanistic Interpretability"},
            {"tag": "Sparse Autoencoder"},
            {"tag": "Robotics"},
        ],
    }

    for attempt in range(5):
        try:
            result = zotero.create_items([payload])
            print(f"Imported successfully! Keys: {result}")
            print(f"Title: {paper['title']}")
            print(f"Authors: {', '.join(a['name'] for a in paper['authors'])}")
            print(f"arXiv: {paper['arxiv_id']}")
            break
        except requests.exceptions.HTTPError as e:
            if "429" in str(e):
                wait = (attempt + 1) * 15
                print(f"Rate limited, retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"HTTP Error: {e}")
                break
        except Exception as e:
            print(f"Import failed: {e}")
            break
else:
    print("Paper already exists in Zotero.")
