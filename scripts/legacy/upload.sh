#!/bin/bash
# Upload file to Zotero attachment - direct PUT approach
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

# Wait to avoid rate limiting
echo "Waiting 120s to avoid rate limiting..."
sleep 120

# Step 1: Create attachment
echo "Step 1: Creating attachment..."
ATTACH_KEY=""
for i in 1 2 3 4 5; do
    if [ $i -gt 1 ]; then
        wait_time=$((i * 20))
        echo "Retry $i, waiting ${wait_time}s..."
        sleep $wait_time
    fi
    
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
        \"mtime\": 0
      }]")
    
    HTTP_CODE=$(echo "$RESP" | tail -1)
    BODY=$(echo "$RESP" | head -n -1)
    
    echo "HTTP: $HTTP_CODE"
    
    if [ "$HTTP_CODE" = "429" ]; then
        echo "Rate limited, retrying..."
        continue
    fi
    
    if [ "$HTTP_CODE" = "200" ]; then
        FAILED=$(echo "$BODY" | python3 -c "import sys, json; d=json.load(sys.stdin); f=d.get('failed',{}); print(len(f))")
        if [ "$FAILED" != "0" ]; then
            echo "Some items failed:"
            echo "$BODY" | python3 -c "import sys, json; d=json.load(sys.stdin); print(json.dumps(d.get('failed',{}), indent=2))"
            continue
        fi
        
        ATTACH_KEY=$(echo "$BODY" | python3 -c "import sys, json; d=json.load(sys.stdin); s=d.get('success',{}); print(list(s.values())[0] if s else 'NO_KEY')")
        echo "Attachment key: $ATTACH_KEY"
        break
    else
        echo "Unexpected status: $HTTP_CODE"
        echo "$BODY" | head -c 300
        break
    fi
done

if [ -z "$ATTACH_KEY" ] || [ "$ATTACH_KEY" = "NO_KEY" ]; then
    echo "Failed to create attachment"
    exit 1
fi

sleep 30

# Step 2: Upload file directly to /items/{key}/file
echo "Step 2: Uploading file directly..."
for i in 1 2 3 4 5; do
    if [ $i -gt 1 ]; then
        wait_time=$((i * 15))
        echo "Retry $i, waiting ${wait_time}s..."
        sleep $wait_time
    fi
    
    HTTP_CODE=$(curl -s -o /tmp/zotero_upload_resp.txt -w "%{http_code}" -X PUT \
      "https://api.zotero.org/users/$ZOTERO_USER_ID/items/$ATTACH_KEY/file" \
      -H "Zotero-API-Key: $ZOTERO_API_KEY" \
      -H "Content-Type: text/markdown" \
      -H "Content-Length: $FILE_SIZE" \
      --data-binary @"$FILE_PATH")
    
    echo "PUT HTTP: $HTTP_CODE"
    if [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "201" ] && [ "$HTTP_CODE" != "204" ]; then
        echo "Response:"
        cat /tmp/zotero_upload_resp.txt | head -c 300
        echo ""
    fi
    
    if [ "$HTTP_CODE" = "429" ]; then
        echo "Rate limited, retrying..."
        continue
    fi
    
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "204" ]; then
        echo "SUCCESS: 论文解读2026-04-13.md uploaded and attached to paper NJQ4H5S5!"
        echo "Attachment key: $ATTACH_KEY"
        exit 0
    fi
    
    if [ "$HTTP_CODE" = "405" ]; then
        echo "Method not allowed, trying GET first..."
        # Try to get upload URL first
        RESP2=$(curl -s -w "\n%{http_code}" "https://api.zotero.org/users/$ZOTERO_USER_ID/items/$ATTACH_KEY/file" \
          -H "Zotero-API-Key: $ZOTERO_API_KEY")
        HTTP2=$(echo "$RESP2" | tail -1)
        BODY2=$(echo "$RESP2" | head -n -1)
        echo "GET HTTP: $HTTP2"
        if [ "$HTTP2" = "200" ]; then
            UPLOAD_URL=$(echo "$BODY2" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('url', 'NO_URL'))")
            echo "Upload URL: ${UPLOAD_URL:0:100}..."
            if [ "$UPLOAD_URL" != "NO_URL" ]; then
                HTTP3=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$UPLOAD_URL" \
                  -H "Content-Type: text/markdown" \
                  --data-binary @"$FILE_PATH")
                echo "Upload HTTP: $HTTP3"
                if [ "$HTTP3" = "200" ] || [ "$HTTP3" = "201" ] || [ "$HTTP3" = "204" ]; then
                    echo "SUCCESS: 论文解读2026-04-13.md uploaded via upload URL!"
                    exit 0
                fi
            fi
        fi
        sleep 15
        continue
    fi
    
    if [ "$HTTP_CODE" = "404" ]; then
        echo "Attachment not ready yet, waiting..."
        sleep 15
        continue
    fi
done

echo "Upload failed after all attempts"
exit 1
