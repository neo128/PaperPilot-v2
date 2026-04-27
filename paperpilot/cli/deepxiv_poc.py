from __future__ import annotations

import argparse
import json
import os

from paperpilot.clients.deepxiv import DeepXivClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DeepXiv PoC client for PaperPilot-v2")
    parser.add_argument("mode", choices=["search", "trending", "brief", "head", "section", "json", "preview"])
    parser.add_argument("query", nargs="?", help="Query string or arXiv id depending on mode")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--section-name", default="Introduction")
    parser.add_argument("--token", help="Override DeepXiv token")
    parser.add_argument("--base-url", help="Override DeepXiv API base URL")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = DeepXivClient(
        token=args.token or os.environ.get("DEEPXIV_TOKEN"),
        base_url=args.base_url or os.environ.get("DEEPXIV_BASE_URL", "https://data.rag.ac.cn"),
    )

    if args.mode == "search":
        result = client.search(args.query or "agent memory", limit=args.limit)
    elif args.mode == "trending":
        result = client.trending(days=args.days, limit=args.limit)
    elif args.mode == "brief":
        result = client.brief(args.query)
    elif args.mode == "head":
        result = client.head(args.query)
    elif args.mode == "section":
        result = client.section(args.query, args.section_name)
    elif args.mode == "json":
        result = client.paper_json(args.query)
    else:
        result = client.preview(args.query)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
