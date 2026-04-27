#!/bin/bash
cd /home/user/.openclaw/workspace/agents/paper/code/PaperPilot-v2
source .venv/bin/activate
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY no_proxy NO_PROXY
python upload_file.py
