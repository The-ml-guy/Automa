"""
Deterministic Editorial Rules and Anti-Slop Linters for Automa (Phases 4, 5, 6).
Evaluates clichés, fake anecdotes, emoji limits, hashtags, and deduplication.
"""

from __future__ import annotations
import hashlib
import re
from typing import List, Set, Tuple, Optional
from pydantic import BaseModel, Field

# Strict list of prohibited buzzwords and generic AI slop
CLICHE_PATTERNS = [
    r"\bdelve\s+(into|deeper)\b",
    r"\bgame[- ]changer\b",
    r"\btestament\s+to\b",
    r"\bskyrocket\b",
    r"\bbuckle\s+up\b",
    r"\brevolutioniz(e|ing|ed)\b",
    r"\bin\s+today's\s+(fast[- ]paced|digital|rapidly\s+changing)\s+(world|age|landscape)\b",
    r"\bsupercharge\b",
    r"\bunleash(\s+the\s+power)?\b",
    r"\belevate\s+your\b",
    r"\bparadigm\s+shift\b",
    r"\bhumbled\s+and\s+honored\b",
    r"\bthrilled\s+to\s+announce\b",
    r"\blet\s+that\s+sink\s+in\b",
    r"\b(agree\?|thoughts\?)\s*$",
    r"\bswipe\s+to\s+see\b",
    r"\bsecret\s+sauce\b",
    r"\bunlock\s+the\s+potential\b",
    r"\bmasterclass\b",
    r"\bgameplan\b",
]

# Patterns detecting fabricated personal case studies, revenue claims, and fake statistics
FABRICATED_CLAIM_PATTERNS = [
    r"\b(?:last\s+week|recently|yesterday),?\s+(?:a|my)\s+client\b",
    r"\b(?:scaled|grew)\s+(?:from|to)\s+\$\d+",
    r"\bmade\s+\$\d+\s+in\s+\d+\s+(?:days|months|hours)\b",
    r"\b(?:studies|research)\s+(?:show|proves?)\s+that\s+\d+%\b",
    r"\b\d+%\s+of\s+(?:developers|engineers|people|companies)\s+(?:fail|struggle|admit)\b",
    r"\bin\s+my\s+\d+\s+years\s+(?:of\s+experience|as\s+a)\b",
    r"\bwe\s+increased\s+revenue\s+by\s+\d+%\b",
]

EMOJI_REGEX = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-a
    "]",
    flags=re.UNICODE,
)


def compute_normalized_fingerprint(text: str, platform: str) -> str:
    """Computes a deterministic SHA-256 hash of normalized text."""
    normalized = re.sub(r"[^\w\s]", "", text.lower())
    normalized = " ".join(normalized.split())
    raw = f"{platform.lower()}::{normalized}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def compute_jaccard_similarity(text_a: str, text_b: str) -> float:
    """Computes word-level Jaccard similarity between two texts."""
    words_a = set(re.findall(r"\b\w{3,}\b", text_a.lower()))
    words_b = set(re.findall(r"\b\w{3,}\b", text_b.lower()))
    if not words_a or not words_b:
        return 0.0
    intersection = words_a.intersection(words_b)
    union = words_a.union(words_b)
    return len(intersection) / len(union)


def count_emojis(text: str) -> int:
    """Returns total number of emoji glyphs found in text."""
    return len(EMOJI_REGEX.findall(text))


def extract_hashtags(text: str) -> List[str]:
    """Returns list of hashtags."""
    return re.findall(r"#\w+", text)


class RuleCheckResult(BaseModel):
    passed: bool
    cliches_found: List[str] = Field(default_factory=list)
    fabricated_claims_found: List[str] = Field(default_factory=list)
    emoji_count: int = 0
    emoji_allowed: int = 2
    hashtag_count: int = 0
    hashtag_allowed: int = 3
    char_count: int = 0
    char_min: Optional[int] = None
    char_max: Optional[int] = None
    duplicate_found: bool = False
    highest_similarity: float = 0.0
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


def check_editorial_rules(
    content: str,
    platform: str,
    constraints: Any,
    existing_texts: List[str],
    has_media: bool = False,
    is_thread: bool = False,
    thread_items: Optional[List[str]] = None,
) -> RuleCheckResult:
    """
    Deterministically validates draft content against editorial rules,
    constraints, clichés, fake anecdotes, and duplication.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Cliché Check
    cliches_found = []
    for pattern in CLICHE_PATTERNS:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            cliches_found.append(match.group(0))
    if cliches_found:
        errors.append(f"Contains prohibited AI slop or buzzwords: {', '.join(cliches_found)}")

    # 2. Fabricated Claims Check
    claims_found = []
    for pattern in FABRICATED_CLAIM_PATTERNS:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            claims_found.append(match.group(0))
    if claims_found:
        errors.append(f"Contains unverified / fabricated personal claims: {', '.join(claims_found)}")

    # 3. Emoji Count
    emoji_cnt = count_emojis(content)
    max_emojis = getattr(constraints, "max_emojis", 2)
    if emoji_cnt > max_emojis:
        errors.append(f"Too many emojis: found {emoji_cnt}, maximum allowed is {max_emojis}")

    # 4. Hashtag Count
    hashtags = extract_hashtags(content)
    max_hashtags = getattr(constraints, "max_hashtags", 3)
    if len(hashtags) > max_hashtags:
        errors.append(f"Too many hashtags: found {len(hashtags)}, maximum allowed is {max_hashtags}")

    # 5. Character Limits
    char_cnt = len(content)
    char_min = getattr(constraints, "min_characters", 50)
    char_max = getattr(constraints, "max_characters", 3000)

    if platform == "x":
        max_tweet = getattr(constraints, "max_characters_per_tweet", 280)
        if is_thread and thread_items:
            for idx, tweet in enumerate(thread_items, 1):
                if len(tweet) > max_tweet:
                    errors.append(f"Tweet {idx} exceeds {max_tweet} characters ({len(tweet)} chars)")
        else:
            if char_cnt > max_tweet:
                errors.append(f"Tweet exceeds {max_tweet} characters ({char_cnt} chars)")
    elif platform == "linkedin":
        if char_cnt < (char_min or 200):
            warnings.append(f"LinkedIn post is shorter than recommended minimum ({char_cnt} chars)")
        if char_cnt > (char_max or 3000):
            errors.append(f"LinkedIn post exceeds maximum limit of {char_max} chars ({char_cnt} chars)")
    elif platform == "instagram":
        ig_max = getattr(constraints, "max_caption_characters", 2200)
        if char_cnt > ig_max:
            errors.append(f"Instagram caption exceeds {ig_max} characters ({char_cnt} chars)")
        # Instagram media constraint check
        require_media = getattr(constraints, "require_media", True)
        if require_media and not has_media:
            errors.append("Instagram requires a verified media asset (image/graphic). Text-only concepts cannot be scheduled.")

    # 6. Duplication & Repetition Check
    duplicate_found = False
    max_similarity = 0.0
    for existing in existing_texts:
        sim = compute_jaccard_similarity(content, existing)
        if sim > max_similarity:
            max_similarity = sim
        if sim >= 0.55:
            duplicate_found = True
            errors.append(f"High content similarity ({sim*100:.1f}%) detected with recent post. Rejecting repetitive concept.")
            break

    passed = len(errors) == 0
    return RuleCheckResult(
        passed=passed,
        cliches_found=cliches_found,
        fabricated_claims_found=claims_found,
        emoji_count=emoji_cnt,
        emoji_allowed=max_emojis,
        hashtag_count=len(hashtags),
        hashtag_allowed=max_hashtags,
        char_count=char_cnt,
        char_min=char_min,
        char_max=char_max,
        duplicate_found=duplicate_found,
        highest_similarity=max_similarity,
        errors=errors,
        warnings=warnings,
    )
