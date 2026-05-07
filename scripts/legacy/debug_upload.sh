#!/bin/bash
# Upload file to Zotero - complete flow with headers inspection
cd /home/user/.openclaw/workspace/agents/paper/code/PaperPilot-v2
source .venv/bin/activate
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY no_proxy NO_PROXY

export ZOTERO_USER_ID=17507734
export ZOTERO_API_KEY="1Okd54r2dTOipn1OvBTWfuYv"
PAPER_KEY="NJQ4H5S5"
FILE_PATH="/home/user/.openclaw/workspace/agents/paper/code/PaperPilot-v2/论文解读2026-04-13.md"
FILE_SIZE=$(wc -c < "$FILE_PATH")
MD5=$(md5sum "$FILE_PATH" | cut -d' ' -f1)

echo "File: $FILE_PATH"
echo "Size: $FILE_SIZE bytes"
echo "MD5: $MD5"
echo ""

echo "Waiting 120s..."
sleep 120

# Step 1: Create attachment and inspect headers
echo "Step 1: Creating attachment..."
RESP_HEADERS=$(mktemp)
RESP_BODY=$(mktemp)

HTTP_CODE=$(curl -s -D "$RESP_HEADERS" -o "$RESP_BODY" -w "%{http_code}" -X POST \
  "https://api.zotero.org/users/$ZOTERO_USER_ID/items" \
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
    \"mtime\": 0
  }]")

echo "HTTP: $HTTP_CODE"
echo "Response headers:"
cat "$RESP_HEADERS"
echo ""
echo "Response body:"
cat "$RESP_BODY" | python3 -m json.tool 2>/dev/null || cat "$RESP_BODY"

# Extract key
ATTACH_KEY=$(cat "$RESP_BODY" | python3 -c "import sys, json; d=json.load(sys.stdin); s=d.get('success',{}); print(list(s.values())[0] if s else 'NO_KEY')" 2>/dev/null)
echo ""
echo "Attachment key: $ATTACH_KEY"

if [ -z "$ATTACH_KEY" ] || [ "$ATTACH_KEY" = "NO_KEY" ]; then
    echo "Failed to create attachment"
    rm -f "$RESP_HEADERS" "$RESP_BODY"
    exit 1
fi

sleep 30

# Step 2: Try to get upload info
echo ""
echo "Step 2: Getting upload info..."
RESP2_HEADERS=$(mktemp)
RESP2_BODY=$(mktemp)

HTTP2=$(curl -s -D "$RESP2_HEADERS" -o "$RESP2_BODY" -w "%{http_code}" \
  "https://api.zotero.org/users/$ZOTERO_USER_ID/items/$ATTACH_KEY/file" \
  -H "Zotero-API-Key: $ZOTERO_API_KEY")

echo "HTTP: $HTTP2"
echo "Response headers:"
cat "$RESP2_HEADERS"
echo ""
echo "Response body:"
cat "$RESP2_BODY" | head -c 500

# Check for upload URL in headers
UPLOAD_LOCATION=$(grep -i "location:" "$RESP2_HEADERS" | tr -d '\r' | cut -d' ' -f2-)
echo ""
echo "Location header: $UPLOAD_LOCATION"

rm -f "$RESP_HEADERS" "$RESP_BODY" "$RESP2_HEADERS" "$RESP2_BODY"
