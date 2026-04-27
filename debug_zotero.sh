#!/bin/bash
# Debug Zotero API
cd /home/user/.openclaw/workspace/agents/paper/code/PaperPilot-v2
source .venv/bin/activate
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY no_proxy NO_PROXY

export ZOTERO_USER_ID=17507734
export ZOTERO_API_KEY="1Okd54r2dTOipn1OvBTWfuYv"
PAPER_KEY="NJQ4H5S5"
FILE_PATH="/home/user/.openclaw/workspace/agents/paper/code/PaperPilot-v2/论文解读2026-04-13.md"
FILE_SIZE=$(wc -c < "$FILE_PATH")
MD5=$(md5sum "$FILE_PATH" | cut -d' ' -f1)

echo "Waiting 120s to avoid rate limiting..."
sleep 120

echo "Creating attachment..."
RESP=$(curl -s -w "\n%{http_code}" -X POST "https://api.zotero.org/users/$ZOTERO_USER_ID/items" \
  -H "Zotero-API-Key: $ZOTERO_API_KEY" \
  -H "Content-Type: application/json" \
  -d "[{
    \"itemType\": \"attachment\",
    \"parentItem\": \"$PAPER_KEY\",
    \"linkMode\": \"imported_file\",
    \"title\": \"论文解读2026-04-13.md\",
    \"contentType\": \"text/markdown\",
    \"filename\": \"论文解读2026-04-13.md\",
    \"md5\": \"$MD5\",
    \"mtime\": 0,
    \"size\": $FILE_SIZE
  }]")

HTTP_CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)

echo "HTTP: $HTTP_CODE"
echo "BODY:"
echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
