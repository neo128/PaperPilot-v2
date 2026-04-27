#!/bin/bash
# Check Zotero attachment
cd /home/user/.openclaw/workspace/agents/paper/code/PaperPilot-v2
source .venv/bin/activate
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY no_proxy NO_PROXY

export ZOTERO_USER_ID=17507734
export ZOTERO_API_KEY="1Okd54r2dTOipn1OvBTWfuYv"

echo "Waiting 120s..."
sleep 120

# Check if attachment exists
ATTACH_KEY="AEK2HENZ"
echo "Checking attachment $ATTACH_KEY..."
curl -s "https://api.zotero.org/users/$ZOTERO_USER_ID/items/$ATTACH_KEY" \
  -H "Zotero-API-Key: $ZOTERO_API_KEY" | python3 -m json.tool 2>/dev/null || echo "Failed"

echo ""
echo "Checking file endpoint..."
RESP=$(curl -s -w "\n%{http_code}" "https://api.zotero.org/users/$ZOTERO_USER_ID/items/$ATTACH_KEY/file" \
  -H "Zotero-API-Key: $ZOTERO_API_KEY")
HTTP=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)
echo "HTTP: $HTTP"
echo "BODY:"
echo "$BODY" | head -c 500
