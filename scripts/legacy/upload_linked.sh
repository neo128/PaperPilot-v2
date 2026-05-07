#!/bin/bash
# Upload file using linked_file mode
cd /home/user/.openclaw/workspace/agents/paper/code/PaperPilot-v2
source .venv/bin/activate
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY no_proxy NO_PROXY

export ZOTERO_USER_ID=17507734
export ZOTERO_API_KEY="1Okd54r2dTOipn1OvBTWfuYv"
PAPER_KEY="NJQ4H5S5"
FILE_PATH="/home/user/.openclaw/workspace/agents/paper/code/PaperPilot-v2/论文解读2026-04-13.md"

echo "File: $FILE_PATH"
echo ""

echo "Waiting 120s..."
sleep 120

# Create attachment with linked_file mode
echo "Creating attachment with linked_file mode..."
RESP=$(curl -s -w "\n%{http_code}" -X POST \
  "https://api.zotero.org/users/$ZOTERO_USER_ID/items" \
  -H "Zotero-API-Key: $ZOTERO_API_KEY" \
  -H "Content-Type: application/json" \
  -d "[{
    \"itemType\": \"attachment\",
    \"parentItem\": \"$PAPER_KEY\",
    \"linkMode\": \"linked_file\",
    \"title\": \"论文解读2026-04-13.md\",
    \"path\": \"storage:$FILE_PATH\"
  }]")

HTTP=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)

echo "HTTP: $HTTP"
echo "BODY:"
echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
