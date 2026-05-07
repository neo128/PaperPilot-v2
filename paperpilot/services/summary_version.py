AI_SUMMARY_VERSION = "v2"


def versioned_ai_summary_label(base: str) -> str:
    return f"{base}-{AI_SUMMARY_VERSION}"
