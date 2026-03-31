"""
TruthCrew Intelligent Image Detection — 6-Phase Investigation Pipeline
=======================================================================
Phase 1: Context Intelligence       — source risk + claim plausibility
Phase 2: Reality Verification       — web search to verify claimed events
Phase 3: Reverse Image Search       — find image origin online
Phase 4: Pixel Forensics            — Claude Vision 6-level analysis
Phase 5: Verdict Engine             — weighted combination + conflict resolution
Phase 6: Trend & Viral Pattern      — check if claim is trending as misinformation

POST /api/detect-image-intelligent
"""

import os
import re
import base64
import logging
import json
import requests
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import anthropic

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Intelligent Image Detection"])

MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_claude_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment")
    return anthropic.Anthropic(api_key=api_key)


def get_search_key() -> str:
    key = os.getenv("SEARCH_API_KEY")
    if not key:
        raise RuntimeError("SEARCH_API_KEY not set")
    return key


def call_sightengine(image_bytes: bytes) -> dict:
    """Call SightEngine genai+deepfake models. Returns se_score 0-100 (higher = more AI)."""
    api_user   = os.getenv("SIGHTENGINE_API_USER")
    api_secret = os.getenv("SIGHTENGINE_API_SECRET")
    if not api_user or not api_secret:
        return {"se_score": 50, "se_confidence": 0, "ai_generated": 0, "deepfake": 0, "available": False}
    try:
        from io import BytesIO
        from PIL import Image as _PIL
        # Compress to 4MB max for SightEngine
        try:
            _img = _PIL.open(BytesIO(image_bytes))
            if _img.mode in ("RGBA", "P"):
                _img = _img.convert("RGB")
            buf = BytesIO()
            _img.save(buf, format="JPEG", quality=85)
            send_bytes = buf.getvalue()
        except Exception:
            send_bytes = image_bytes

        resp = requests.post(
            "https://api.sightengine.com/1.0/check.json",
            data={"models": "genai,deepfake", "api_user": api_user, "api_secret": api_secret},
            files={"media": ("image.jpg", send_bytes, "image/jpeg")},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        ai_gen   = round(float(data.get("type", {}).get("ai_generated", 0)) * 100)
        deepfake = round(float(data.get("type", {}).get("deepfake",      0)) * 100)
        se_score = max(ai_gen, deepfake)
        se_confidence = round(abs(se_score - 50) * 2)   # 0=uncertain, 100=fully certain
        logger.info(f"SightEngine: ai_generated={ai_gen}%, deepfake={deepfake}%, se_score={se_score}%")
        return {"se_score": se_score, "se_confidence": se_confidence,
                "ai_generated": ai_gen, "deepfake": deepfake, "available": True}
    except Exception as e:
        logger.warning(f"SightEngine call failed: {e}")
        return {"se_score": 50, "se_confidence": 0, "ai_generated": 0, "deepfake": 0, "available": False}


def serper_search(query: str, num: int = 5) -> list[dict]:
    """Run a Google search via SerpAPI. Returns list of result dicts."""
    try:
        api_key = get_search_key()
        resp = requests.get(
            "https://serpapi.com/search",
            params={
                "q":       query,
                "num":     num,
                "api_key": api_key,
                "engine":  "google",
            },
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for r in data.get("organic_results", []):
            results.append({
                "title":   r.get("title", ""),
                "link":    r.get("link", ""),
                "snippet": r.get("snippet", ""),
            })
        return results
    except Exception as e:
        logger.warning(f"SerpAPI search failed: {e}")
        return []


def compress_image(image_bytes: bytes, max_bytes: int = 800_000) -> bytes:
    """Compress image to fit Claude's limits."""
    from PIL import Image
    from io import BytesIO
    if len(image_bytes) <= max_bytes:
        return image_bytes
    img = Image.open(BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    quality = 85
    while quality >= 40:
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= max_bytes:
            return buf.getvalue()
        quality -= 10
    # Resize
    w, h = img.size
    while w > 800:
        w, h = int(w * 0.75), int(h * 0.75)
        buf = BytesIO()
        img.resize((w, h), Image.LANCZOS).save(buf, format="JPEG", quality=75)
        if buf.tell() <= max_bytes:
            return buf.getvalue()
    buf = BytesIO()
    img.resize((640, 480), Image.LANCZOS).save(buf, format="JPEG", quality=65)
    return buf.getvalue()


CREDIBLE_DOMAINS = [
    "reuters.com", "apnews.com", "bbc.com", "ndtv.com", "thehindu.com",
    "indianexpress.com", "espncricinfo.com", "cricbuzz.com", "gettyimages.com",
    "hindustantimes.com", "timesofindia.indiatimes.com", "news18.com",
    "livemint.com", "firstpost.com", "theguardian.com", "nytimes.com",
    "bcci.tv", "iplt20.com", "pti.in", "ani.in"
]

AI_PLATFORMS = [
    "midjourney.com", "civitai.com", "lexica.art", "playground.ai",
    "nightcafe.studio", "openart.ai", "deviantart.com", "artbreeder.com",
    "stability.ai", "huggingface.co/spaces"
]

FACTCHECK_DOMAINS = [
    "altnews.in", "boomlive.in", "thequint.com/news/webqoof",
    "indiatoday.in/fact-check", "factchecker.in", "vishvasnews.com"
]

SOURCE_RISK = {
    "whatsapp": 80, "telegram": 75, "someone sent me": 80,
    "family group": 80, "forward": 75, "facebook": 55,
    "instagram": 50, "twitter": 45, "x.com": 45,
    "youtube": 40, "news website": 20, "google": 35,
    "i took": 5, "i clicked": 5, "screenshot": 60,
    "reddit": 45, "email": 65, "unknown": 70
}


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1: CONTEXT INTELLIGENCE
# ─────────────────────────────────────────────────────────────────────────────

def phase1_context(
    source: str,
    description: str,
    suspicion: str,
    claims: str,
) -> dict:
    """
    Analyse context provided by the user.
    Returns context_score (0-100, higher = more suspicious) + reasoning.
    """
    score = 0
    reasons = []
    search_queries = []

    # Source risk
    source_lower = (source or "unknown").lower()
    source_score = 70  # default unknown
    for keyword, risk in SOURCE_RISK.items():
        if keyword in source_lower:
            source_score = risk
            break
    score += source_score * 0.4
    if source_score >= 70:
        reasons.append(f"High-risk source: {source} — commonly used to spread AI fakes")
    elif source_score >= 50:
        reasons.append(f"Medium-risk source: {source}")
    else:
        reasons.append(f"Low-risk source: {source}")

    # Claim plausibility
    claim_text = f"{description} {claims}".strip().lower()

    high_risk_patterns = [
        ("celebrity", "cricket"),
        ("bollywood", "sport"),
        ("politician", "arrest"),
        ("prime minister", "announce"),
        ("actor", "training"),
        ("cm ", "resign"),
        ("minister", "scandal"),
    ]
    for pat in high_risk_patterns:
        if all(p in claim_text for p in pat):
            score += 15
            reasons.append(f"Claim matches high-risk misinformation pattern: {' + '.join(pat)}")
            break

    # User themselves is suspicious
    if suspicion and len(suspicion) > 5:
        score += 10
        reasons.append("User flagged visual anomalies — trust user's instinct")

    score = min(100, score)

    # Generate search queries for Phase 2
    if description:
        search_queries.append(f"{description} real photo")
        search_queries.append(f"{description} fake AI generated")
        search_queries.append(f"{description} fact check")
    if claims:
        search_queries.append(f"{claims} news")
        search_queries.append(f"{claims} fake")

    return {
        "score": round(score),
        "reasoning": reasons,
        "search_queries": search_queries[:5],
        "source_risk": source_score,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2: REALITY VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def phase2_reality(search_queries: list[str], description: str, claims: str) -> dict:
    """
    Search the web to verify if the claimed event/person/scenario is real.
    Returns reality_score (0-100, higher = more likely REAL).
    """
    if not search_queries and not description and not claims:
        return {"score": 50, "reasoning": ["No claims provided — skipping reality check"], "findings": []}

    all_results = []
    queries_to_run = search_queries[:3]

    if description and not queries_to_run:
        queries_to_run = [
            f"{description} news",
            f"{description} real event",
            f"{description} fake AI"
        ]

    for q in queries_to_run:
        results = serper_search(q, num=5)
        all_results.extend(results)

    if not all_results:
        return {"score": 50, "reasoning": ["Web search unavailable — treating as neutral"], "findings": []}

    # Analyse results
    credible_hits = []
    factcheck_hits = []
    ai_hits = []
    debunk_hits = []

    for r in all_results:
        link = r.get("link", "").lower()
        title = r.get("title", "").lower()
        snippet = r.get("snippet", "").lower()

        for d in CREDIBLE_DOMAINS:
            if d in link:
                credible_hits.append(r)
                break
        for d in FACTCHECK_DOMAINS:
            if d in link:
                factcheck_hits.append(r)
                break
        for d in AI_PLATFORMS:
            if d in link:
                ai_hits.append(r)
                break
        if any(w in title + snippet for w in ["fake", "ai generated", "morphed", "debunked", "fact check", "false"]):
            debunk_hits.append(r)

    reasoning = []
    score = 50  # neutral start

    if debunk_hits and len(debunk_hits) >= 3:
        score -= 40
        reasoning.append(f"{len(debunk_hits)} search results contain 'fake/AI/debunked' language — strong signal this claim is known misinformation")
    elif debunk_hits:
        score -= 20
        reasoning.append(f"Some search results contain 'fake/AI/debunked' language about this claim")

    if factcheck_hits:
        score -= 30
        reasoning.append(f"Found on fact-check sites — may have been previously debunked")

    if ai_hits:
        score -= 30
        reasoning.append(f"Similar content found on AI art platforms — strong AI generation signal")

    if credible_hits and not debunk_hits and not factcheck_hits:
        score += 25
        reasoning.append(f"Found {len(credible_hits)} credible news source(s) covering this — signal of authenticity")
    elif credible_hits and debunk_hits:
        reasoning.append(f"Mixed signals — found on credible sources but also debunk language present")

    if not credible_hits and not factcheck_hits and not ai_hits and not debunk_hits:
        score = 40
        reasoning.append("No credible news coverage found — if this were a real notable event, it would likely be covered")

    score = max(0, min(100, score))

    return {
        "score": score,
        "reasoning": reasoning,
        "findings": {
            "credible_hits": len(credible_hits),
            "factcheck_hits": len(factcheck_hits),
            "ai_platform_hits": len(ai_hits),
            "debunk_hits": len(debunk_hits),
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3: REVERSE IMAGE SEARCH
# ─────────────────────────────────────────────────────────────────────────────

def phase3_reverse_search(description: str) -> dict:
    """
    Search for the image online using description-based queries.
    Returns origin_score (0-100, higher = more likely REAL).
    """
    if not description:
        return {"score": 50, "reasoning": ["No description provided — skipping reverse search"], "findings": {}}

    queries = [
        f"{description} site:reuters.com OR site:apnews.com OR site:gettyimages.com",
        f"{description} image original source",
        f"{description} AI generated fake viral",
    ]

    all_results = []
    for q in queries[:2]:
        results = serper_search(q, num=5)
        all_results.extend(results)

    credible_hits = []
    ai_hits = []
    factcheck_hits = []

    for r in all_results:
        link = r.get("link", "").lower()
        for d in CREDIBLE_DOMAINS:
            if d in link:
                credible_hits.append(r)
                break
        for d in AI_PLATFORMS:
            if d in link:
                ai_hits.append(r)
                break
        for d in FACTCHECK_DOMAINS:
            if d in link:
                factcheck_hits.append(r)
                break

    score = 50
    reasoning = []

    if ai_hits:
        score = 15
        reasoning.append(f"Similar content found on AI art platforms — likely AI-generated")
    elif factcheck_hits:
        score = 20
        reasoning.append("Description matches previously fact-checked (debunked) content")
    elif credible_hits and len(credible_hits) >= 2:
        score = 75
        reasoning.append(f"Found on multiple credible news sources — strong signal of authenticity")
    elif credible_hits:
        score = 50
        reasoning.append(f"Found on 1 credible source — topic exists but this specific image not verified")
    else:
        score = 45
        reasoning.append("Not found on credible or AI platforms — neutral signal")

    return {
        "score": score,
        "reasoning": reasoning,
        "findings": {
            "credible_hits": len(credible_hits),
            "ai_hits": len(ai_hits),
            "factcheck_hits": len(factcheck_hits),
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4: PIXEL FORENSICS — Claude Vision
# ─────────────────────────────────────────────────────────────────────────────

def phase4_pixel_forensics(image_bytes: bytes, description: str = "") -> dict:
    """
    6-level pixel forensics using Claude Vision.
    Returns pixel_score (0-100, higher = more likely AI).
    """
    client = get_claude_client()
    # Detect actual image type
    from PIL import Image as PILImage
    from io import BytesIO as _BytesIO
    try:
        _img = PILImage.open(_BytesIO(image_bytes))
        _fmt = (_img.format or "JPEG").upper()
        media_type = {"PNG": "image/png", "JPEG": "image/jpeg",
                      "WEBP": "image/webp", "GIF": "image/gif"}.get(_fmt, "image/jpeg")
        # Convert PNG to JPEG for compression efficiency
        if _fmt == "PNG":
            _buf = _BytesIO()
            _img.convert("RGB").save(_buf, format="JPEG", quality=90)
            image_bytes = _buf.getvalue()
            media_type = "image/jpeg"
    except Exception:
        media_type = "image/jpeg"

    compressed = compress_image(image_bytes)
    b64 = base64.standard_b64encode(compressed).decode("utf-8")

    prompt = f"""You are a world-class forensic image investigator with 20 years of experience detecting AI-generated, deepfake, and manipulated media. You have analysed over 100,000 images. You think like a detective, not a classifier.

{f'CLAIMED CONTEXT: {description}' if description else 'No context provided — first determine what this image claims to show.'}

YOUR MISSION: Determine if this image is AI-generated, manipulated, or a genuine photograph.

IMPORTANT MINDSET:
- AI generators fool the eye but not physics, biology, or logic
- Look for what is WRONG, not just what looks suspicious
- Real photos have imperfections — dirt, wear, asymmetry, motion blur, noise
- AI images are too clean, too perfect, too composed
- Ask yourself: "Could this exact scene exist in the real world right now?"

STEP 1 — FIRST IMPRESSION (before detailed analysis):
What does this image claim to show? Does the overall scene feel real or staged? What is your gut reaction and why?

STEP 2 — UNIVERSAL 5-SIGNAL CHECK (works for ANY image type):

SIGNAL A — PHYSICS REALITY:
- Does light come from ONE consistent source and hit ALL objects/people the same way?
- Do shadows point in the same direction for everything in the scene?
- Does gravity affect hair, fabric, objects correctly?
- Is perspective and depth mathematically consistent?
- Does water, smoke, fire, or weather behave physically correctly?
Score A: 0-100 (higher = more AI-like). Finding:

SIGNAL B — BIOLOGICAL AUTHENTICITY:
- Count every finger on every visible hand. Are there exactly 5? Are joints natural?
- Do faces have natural asymmetry? (Perfect symmetry = AI red flag)
- Is skin texture age-appropriate with real pores, wrinkles, variation?
- Do eyes have natural reflections consistent with the light source?
- Does hair have individual strands or blobby, painted-on appearance?
- Are teeth natural with slight imperfections or unnaturally perfect?
Score B: 0-100. Finding:

SIGNAL C — CONTACT POINT PHYSICS (most powerful AI detector):
THIS IS WHERE AI FAILS MOST. Examine EVERY place where two things touch:
- Hand on shoulder: does fabric compress and deform naturally?
- Person holding object: do fingers wrap with correct physics?
- Two people touching: is there unnatural blending or merging at boundaries?
- Feet on ground: is there proper weight distribution and shadow?
- Clothing on body: do folds follow both gravity AND body movement?
AI cannot simulate true physical contact — it blends instead of deforms.
Score C: 0-100. Finding:

SIGNAL D — DETAIL CONSISTENCY:
- Read ALL text in the image — is it real words or gibberish?
- Are logos/brands consistent across the entire image? (Same jersey worn by 3 people should have IDENTICAL logos)
- Are small details (buttons, zippers, stitching, watch faces) rendered correctly?
- Do repeating elements (tiles, bricks, crowd faces) show natural variation or suspicious repetition?
- Is the background coherent or does it have impossible architecture/blending?
Score D: 0-100. Finding:

SIGNAL E — THE PERFECTION TEST:
Real world is imperfect. Ask:
- Is there any dirt, dust, wear, scratches, or natural aging?
- Is lighting TOO perfect — like a studio instead of real environment?
- Are colours TOO vivid or skin tones TOO smooth?
- Is composition TOO well-framed for a candid moment?
- Does everything look like it was placed deliberately rather than naturally?
- Is there natural motion blur where there should be (sports, movement)?
Score E: 0-100. Finding:

STEP 3 — IMAGE TYPE SPECIFIC DEEP DIVE:
Based on what you see, classify as: PORTRAIT / GROUP / LANDSCAPE / PRODUCT / ACTION / DOCUMENT / MEME
Then apply the most relevant additional checks for that type:
- GROUP: Are the interactions between people physically believable?
- LANDSCAPE: Does the environment obey real-world geography and weather?
- DOCUMENT: Is all text readable, consistent, and properly formatted?
- ACTION/SPORTS: Is motion blur present and consistent with the claimed movement?

STEP 4 — ABSENCE ANALYSIS:
What should logically be present in this scene but is MISSING?
Real environments have background complexity — other people, equipment, imperfections.
AI images often have suspiciously empty or generic backgrounds.

STEP 5 — CROSS-REFERENCE CHECK:
Do ALL elements agree with each other?
- Does face lighting match background lighting?
- Does clothing condition match the claimed activity?
- Does the setting match the claimed time/place/event?
- Do multiple people in the scene share consistent lighting/shadow angles?

Now provide your final structured output:

IMAGE_TYPE: <PORTRAIT/GROUP/LANDSCAPE/PRODUCT/ACTION/DOCUMENT/MEME>
PEOPLE_COUNT: <number of people visible, 0 if none>
CONTACT_ZONES: <number of places where people/objects physically touch each other, 0 if none>
SCORES: L1=<Signal A> L2=<Signal B> L3=<Signal C> L4=<Signal D> L5=<Signal E> L6=<Step3 score>
KEY_EVIDENCE: <The single most important finding that determined your verdict — be specific>
OVERALL_PIXEL_SCORE: <Final weighted 0-100, higher = more AI-generated>
AUTO_DESCRIPTION: <In 1 sentence, describe exactly what this image shows — used for web verification>

Be brutally honest. If something is wrong, say exactly what and where."""

    import time
    last_error = None
    response = None
    models_to_try = [
        ("claude-sonnet-4-6", 3),        # try Sonnet 3 times
        ("claude-haiku-4-5-20251001", 2), # fallback to Haiku 2 times
    ]
    for model_name, attempts in models_to_try:
        for attempt in range(attempts):
            try:
                response = client.messages.create(
                    model=model_name,
                    max_tokens=1000,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": b64,
                                }
                            },
                            {"type": "text", "text": prompt}
                        ]
                    }]
                )
                logger.info(f"Phase 4 using model: {model_name}")
                break
            except Exception as e:
                last_error = e
                if "overloaded" in str(e).lower() or "529" in str(e):
                    logger.warning(f"Claude overloaded ({model_name}), retry {attempt+1}/{attempts}...")
                    time.sleep(3)
                    continue
                raise e
        if response is not None:
            break
    if response is None:
        raise last_error
    try:
        text = response.content[0].text

        # Extract scores
        scores_match   = re.search(r'SCORES:\s*L1=(\d+)[,\s]+L2=(\d+)[,\s]+L3=(\d+)[,\s]+L4=(\d+)[,\s]+L5=(\d+)[,\s]+L6=(\d+)', text, re.DOTALL)
        overall_match  = re.search(r'OVERALL_PIXEL_SCORE:\s*(\d+)', text)
        type_match     = re.search(r'IMAGE_TYPE:\s*(\w+)', text)
        evidence_match = re.search(r'KEY_EVIDENCE:\s*(.+)', text)
        people_match   = re.search(r'PEOPLE_COUNT:\s*(\d+)', text)
        contact_match  = re.search(r'CONTACT_ZONES:\s*(\d+)', text)

        people_count  = int(people_match.group(1))  if people_match  else 0
        contact_zones = int(contact_match.group(1)) if contact_match else 0

        level_scores = {}
        if scores_match:
            level_scores = {
                "L1": int(scores_match.group(1)),
                "L2": int(scores_match.group(2)),
                "L3": int(scores_match.group(3)),
                "L4": int(scores_match.group(4)),
                "L5": int(scores_match.group(5)),
                "L6": int(scores_match.group(6)),
            }

        # Adaptive weights by image type — GROUP_3+ gets highest contact weight
        img_type = type_match.group(1).upper() if type_match else "UNKNOWN"
        if img_type == "GROUP" and people_count >= 3:
            img_type = "GROUP_3+"
        weights = {
            "GROUP":    {"L1":10,"L2":20,"L3":25,"L4":15,"L5":10,"L6":20},
            "GROUP_3+": {"L1": 8,"L2":18,"L3":30,"L4":14,"L5":10,"L6":20},
            "PORTRAIT": {"L1":10,"L2":30,"L3":10,"L4":10,"L5":10,"L6":30},
            "ACTION":   {"L1":10,"L2":18,"L3":28,"L4":12,"L5": 8,"L6":24},
            "LANDSCAPE":{"L1":20,"L2": 0,"L3": 8,"L4": 8,"L5":25,"L6":39},
            "PRODUCT":  {"L1":15,"L2": 0,"L3":12,"L4":22,"L5":15,"L6":36},
            "DOCUMENT": {"L1": 8,"L2": 0,"L3": 0,"L4":45,"L5":17,"L6":30},
            "MEME":     {"L1":10,"L2": 0,"L3": 5,"L4":40,"L5":15,"L6":30},
            "SCREENSHOT":{"L1":10,"L2":0,"L3": 0,"L4":45,"L5":20,"L6":25},
        }.get(img_type, {"L1":15,"L2":20,"L3":15,"L4":15,"L5":15,"L6":20})

        # Compute weighted score
        if level_scores:
            weighted = sum(level_scores.get(f"L{i}", 50) * weights.get(f"L{i}", 16) / 100
                          for i in range(1, 7))
            pixel_score = round(min(100, weighted))
        elif overall_match:
            pixel_score = int(overall_match.group(1))
        else:
            pixel_score = 50

        key_evidence    = evidence_match.group(1).strip() if evidence_match else "Analysis complete"
        auto_desc_match = re.search(r'AUTO_DESCRIPTION:\s*(.+)', text)
        auto_description= auto_desc_match.group(1).strip() if auto_desc_match else ""

        return {
            "score":            pixel_score,
            "image_type":       img_type,
            "people_count":     people_count,
            "contact_zones":    contact_zones,
            "level_scores":     level_scores,
            "key_evidence":     key_evidence,
            "auto_description": auto_description,
            "full_analysis":    text[:1200],
        }

    except Exception as e:
        logger.error(f"Phase 4 Claude Vision error: {e}")
        return {"score": 50, "image_type": "UNKNOWN", "level_scores": {},
                "key_evidence": "Vision analysis unavailable", "full_analysis": ""}


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6: TREND & VIRAL PATTERN DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def phase6_trend_viral(description: str, claims: str) -> dict:
    """
    Check if the claim/topic is currently trending as misinformation.
    Returns trend_score (0-100, higher = more suspicious/trending as fake).
    """
    if not description and not claims:
        return {"score": 50, "reasoning": ["No description — skipping trend check"], "trending_fakes": []}

    search_term = f"{description} {claims}".strip()
    queries = [
        f"{search_term} fake viral WhatsApp 2026",
        f"{search_term} AI generated trending India",
        f"fact check {search_term} altnews boom",
    ]

    all_results = []
    for q in queries[:2]:
        results = serper_search(q, num=5)
        all_results.extend(results)

    score = 30  # baseline — most claims are not trending fakes
    reasoning = []
    trending_fakes = []

    for r in all_results:
        link  = r.get("link", "").lower()
        title = r.get("title", "").lower()
        snip  = r.get("snippet", "").lower()
        combined = title + " " + snip

        # Factcheck sites found
        for d in FACTCHECK_DOMAINS:
            if d in link:
                score += 25
                trending_fakes.append(r.get("title", ""))
                reasoning.append(f"Similar claim already debunked by fact-checkers: {r.get('title','')[:80]}")
                break

        # Strong viral fake keywords
        if any(w in combined for w in ["viral fake", "morphed", "ai generated viral", "debunked", "misleading claim"]):
            score += 15
            reasoning.append(f"Search results show this topic is trending as misinformation")

        # WhatsApp viral pattern
        if "whatsapp" in combined and any(w in combined for w in ["fake", "false", "misleading"]):
            score += 10
            reasoning.append("Topic is associated with WhatsApp misinformation spread")

    if not trending_fakes and score <= 35:
        reasoning.append("No trending misinformation patterns found for this topic")

    score = min(100, score)

    return {
        "score":          score,
        "reasoning":      list(set(reasoning))[:4],
        "trending_fakes": trending_fakes[:3],
    }


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5: VERDICT ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def phase5_verdict(
    p1: dict,        # context
    p2: dict,        # reality  (higher = more real → inverted internally)
    p3: dict,        # reverse search (higher = more real → inverted internally)
    p4: dict,        # pixel    (higher = more AI)
    p6: dict,        # trend    (higher = more suspicious)
    se_result: dict, # SightEngine result
) -> dict:
    """
    Adaptive fusion engine — combines pipeline (phases 1-4) with SightEngine.
    SightEngine weight is NOT fixed: it adapts based on image type, SE confidence,
    reality evidence strength, and pipeline vs SE conflict pattern.
    """
    # ── Normalise all scores → higher = more AI ─────────────────────────────
    context_ai = p1["score"]
    reality_ai = 100 - p2["score"]
    search_ai  = 100 - p3["score"]
    pixel_ai   = p4["score"]
    trend_ai   = p6["score"]

    findings           = p2.get("findings", {}) if isinstance(p2.get("findings"), dict) else {}
    reality_verdict_s  = p2.get("reality_verdict", "UNVERIFIABLE")
    origin_verdict_s   = p3.get("origin_verdict",  "NO_MATCHES_FOUND")

    # ── Pipeline internal weights (sum = 100) ────────────────────────────────
    w = {"context": 10, "reality": 30, "search": 10, "pixel": 50}

    # No context → drop context weight, boost pixel
    if p1.get("source_risk", 50) == 70 and len(p1.get("reasoning", [])) <= 1:
        w["context"] = 3
        w["pixel"]  += 7

    # Strong reality evidence → boost reality weight
    if reality_verdict_s in ("VERIFIED_REAL", "LIKELY_FABRICATED"):
        w["reality"] = 35
        w["pixel"]  -= 5

    # Reverse search found on credible sources
    if origin_verdict_s == "FOUND_ON_CREDIBLE_SOURCES":
        w["search"]  = 18
        w["pixel"]  -= 8
    elif origin_verdict_s == "FOUND_ON_AI_PLATFORMS":
        w["search"]  = 22
        w["pixel"]  -= 12
    elif origin_verdict_s == "NO_MATCHES_FOUND":
        # Redistribute — no search signal to use
        w["reality"] += 5
        w["pixel"]   += 5
        w["search"]   = 0

    # Renormalise to 100
    total_w = sum(w.values())
    for k in w:
        w[k] = round(w[k] / total_w * 100, 1)

    pipeline_score = (
        context_ai * w["context"] / 100 +
        reality_ai * w["reality"] / 100 +
        search_ai  * w["search"]  / 100 +
        pixel_ai   * w["pixel"]   / 100
    )

    # ── Adaptive SightEngine weight ──────────────────────────────────────────
    se_score      = se_result.get("se_score",      50)
    se_confidence = se_result.get("se_confidence",  0)
    se_available  = se_result.get("available",    False)
    se_conflict   = "SE_UNAVAILABLE"

    if not se_available:
        final_score       = pipeline_score
        final_se_weight   = 0.0
    else:
        # Factor A: base weight by image type
        SE_TYPE_WEIGHTS = {
            "PORTRAIT":   0.35,
            "GROUP":      0.20,
            "GROUP_3+":   0.15,   # SE is WORST for crowd contact zones
            "LANDSCAPE":  0.30,
            "PRODUCT":    0.30,
            "SCREENSHOT": 0.25,
            "DOCUMENT":   0.20,
            "MEME":       0.20,
            "ACTION":     0.18,
        }
        img_type      = p4.get("image_type", "UNKNOWN")
        se_type_wt    = SE_TYPE_WEIGHTS.get(img_type, 0.25)

        # Factor B: reduce SE weight when SE itself is unsure
        if se_confidence < 40:
            se_type_wt *= 0.6
        elif se_confidence < 60:
            se_type_wt *= 0.8

        # Factor C: hard reality evidence overrides SE
        if reality_verdict_s in ("VERIFIED_REAL", "LIKELY_FABRICATED"):
            se_type_wt *= 0.5

        # Factor D: conflict pattern
        pipeline_says_ai = pipeline_score > 55
        se_says_ai       = se_score > 50
        if pipeline_says_ai and not se_says_ai:
            se_type_wt *= 0.7
            se_conflict = "PIPELINE_CAUGHT_SE_MISSED"
        elif se_says_ai and not pipeline_says_ai:
            se_type_wt *= 1.2
            se_conflict = "SE_CAUGHT_PIPELINE_MISSED"
        elif pipeline_says_ai and se_says_ai:
            se_conflict = "BOTH_AGREE_AI"
        else:
            se_conflict = "BOTH_AGREE_REAL"

        # Clamp SE weight 5 – 40 %
        final_se_weight      = max(0.05, min(0.40, se_type_wt))
        final_pipeline_weight = 1.0 - final_se_weight
        final_score = pipeline_score * final_pipeline_weight + se_score * final_se_weight

    # ── Conflict resolution floor / cap adjustments ──────────────────────────
    conflict_flags = []

    # Conflict B: reality says fabricated + pixels look clean → floor at 65
    if reality_verdict_s == "LIKELY_FABRICATED" and pixel_ai < 50:
        final_score = max(final_score, 65)
        conflict_flags.append("Reality verification found fabrication evidence — overriding clean pixel signal")

    # Conflict D: found on credible sources + pixels flagged → cap at 45
    if origin_verdict_s == "FOUND_ON_CREDIBLE_SOURCES" and pixel_ai > 60:
        final_score = min(final_score, 45)
        conflict_flags.append("Image found on credible news sources — pixel artifacts likely compression, not AI")

    # Conflict E: already debunked by fact-checkers → floor at 80
    if findings.get("factcheck_hits", 0) > 0:
        final_score = max(final_score, 80)
        conflict_flags.append("Fact-checkers have already confirmed this as fake content")

    # Conflict F: user took the photo themselves → cap at 25
    if p1.get("source_risk", 100) <= 5:
        final_score = min(final_score, 25)
        conflict_flags.append("User claims to have taken this photo — treating as likely genuine")

    final_score = max(0, min(100, round(final_score)))

    # ── Confidence calculation ───────────────────────────────────────────────
    votes = [
        context_ai > 55,
        reality_ai > 55,
        search_ai  > 55,
        pixel_ai   > 55,
        (se_score > 50 if se_available else final_score > 50),
    ]
    ai_votes = sum(votes)
    majority = max(ai_votes, 5 - ai_votes)

    if majority >= 4:
        conf_pct   = min(95, 65 + majority * 6)
        confidence = "HIGH"
    elif majority >= 3:
        conf_pct   = 45 + majority * 5
        confidence = "MEDIUM"
    else:
        conf_pct   = max(15, 25 + majority * 5)
        confidence = "LOW"

    # Reduce confidence when pipeline and SE disagree
    if se_conflict in ("PIPELINE_CAUGHT_SE_MISSED", "SE_CAUGHT_PIPELINE_MISSED"):
        conf_pct = max(15, conf_pct - 15)

    # ── Verdict ──────────────────────────────────────────────────────────────
    if final_score >= 80:
        verdict, verdict_label = "AI_GENERATED", "Almost certainly AI-generated"
    elif final_score >= 60:
        verdict, verdict_label = "LIKELY_AI",    "Likely AI-generated"
    elif final_score >= 40:
        verdict, verdict_label = "UNCERTAIN",    "Cannot determine — may be real or AI"
    elif final_score >= 20:
        verdict, verdict_label = "LIKELY_REAL",  "Likely a genuine photograph"
    else:
        verdict, verdict_label = "REAL",         "Almost certainly genuine"

    return {
        "final_score":      final_score,
        "verdict":          verdict,
        "verdict_label":    verdict_label,
        "confidence":       confidence,
        "confidence_pct":   conf_pct,
        "pipeline_score":   round(pipeline_score),
        "se_score":         se_score,
        "se_weight_used":   round(final_se_weight * 100, 1) if se_available else 0,
        "se_conflict":      se_conflict,
        "weights_used":     {k: round(v, 1) for k, v in w.items()},
        "phase_scores": {
            "context":  context_ai,
            "reality":  reality_ai,
            "search":   search_ai,
            "pixel":    pixel_ai,
            "trend":    trend_ai,
        },
        "conflicts": conflict_flags,
    }


def build_summary(verdict_result: dict, p1: dict, p2: dict, p4: dict, p6: dict,
                  source: str, description: str) -> dict:
    """Build human-readable summary in English, Hindi, Marathi."""
    v     = verdict_result["verdict_label"]
    conf  = verdict_result["confidence"]
    score = verdict_result["final_score"]

    # Filter out generic/useless filler strings
    SKIP_PHRASES = {
        "analysis complete", "vision analysis unavailable", "no description provided",
        "no claims provided", "skipping", "unavailable", "none",
    }
    def clean(s: str) -> str:
        if not s: return ""
        return "" if any(p in s.lower() for p in SKIP_PHRASES) else s.strip(" .")

    key_evidence  = clean(p4.get("key_evidence", ""))
    conflict_note = clean(verdict_result["conflicts"][0]) if verdict_result["conflicts"] else ""

    # Pick the most informative reality reasoning line (skip generic skipped lines)
    reality_note = ""
    for r in p2.get("reasoning", []):
        c = clean(r)
        if c:
            reality_note = c
            break

    # Pick the most informative trend reasoning line
    trend_note = ""
    for r in p6.get("reasoning", []):
        c = clean(r)
        if c:
            trend_note = c
            break

    # Source label
    src_label = source.replace("_", " ").title() if source else "Unknown source"

    # Build English sentence by sentence, only including non-empty parts
    parts_en = [f"This image was received via {src_label}."]
    if description:
        parts_en.append(f"It claims to show: {description}.")
    if reality_note:
        parts_en.append(reality_note + ".")
    if key_evidence:
        parts_en.append(f"Pixel forensics finding: {key_evidence}.")
    if trend_note:
        parts_en.append(trend_note + ".")
    if conflict_note:
        parts_en.append(f"Note: {conflict_note}.")
    parts_en.append(f"Verdict: {v}. Confidence: {conf} ({score}/100).")
    en = " ".join(parts_en)

    # Hindi
    parts_hi = [f"यह छवि {src_label} के माध्यम से प्राप्त हुई।"]
    if description:
        parts_hi.append(f"दावा: {description}।")
    if reality_note:
        parts_hi.append(f"वेब जाँच: {reality_note[:80]}।")
    if key_evidence:
        parts_hi.append(f"पिक्सेल विश्लेषण: {key_evidence[:80]}।")
    if trend_note:
        parts_hi.append(f"ट्रेंड: {trend_note[:80]}।")
    if conflict_note:
        parts_hi.append(f"विशेष: {conflict_note[:80]}।")
    parts_hi.append(f"निर्णय: {v}। विश्वास स्तर: {conf} ({score}/100)।")
    hi = " ".join(parts_hi)

    # Marathi
    parts_mr = [f"ही प्रतिमा {src_label} द्वारे मिळाली।"]
    if description:
        parts_mr.append(f"दावा: {description}।")
    if reality_note:
        parts_mr.append(f"वेब तपासणी: {reality_note[:80]}।")
    if key_evidence:
        parts_mr.append(f"पिक्सेल विश्लेषण: {key_evidence[:80]}।")
    if trend_note:
        parts_mr.append(f"ट्रेंड: {trend_note[:80]}।")
    if conflict_note:
        parts_mr.append(f"विशेष: {conflict_note[:80]}।")
    parts_mr.append(f"निर्णय: {v}। विश्वास पातळी: {conf} ({score}/100)।")
    mr = " ".join(parts_mr)

    return {"english": en, "hindi": hi, "marathi": mr}


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/detect-image-intelligent")
async def detect_image_intelligent(
    image:       UploadFile = File(...),
    source:      Optional[str] = Form(default=""),
    description: Optional[str] = Form(default=""),
    suspicion:   Optional[str] = Form(default=""),
    claims:      Optional[str] = Form(default=""),
):
    """
    6-phase intelligent image detection pipeline.
    - image: uploaded image file
    - source: where user got the image (whatsapp / instagram / news website / etc.)
    - description: what the image claims to show
    - suspicion: why user thinks it might be fake
    - claims: text claims made about this image
    """
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Must be an image file")

    image.file.seek(0, os.SEEK_END)
    size = image.file.tell()
    image.file.seek(0)
    if size > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail=f"Image too large ({size/1024/1024:.1f}MB). Max 20MB.")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file")

    try:
        logger.info(f"Intelligent detection started — source={source}, desc={description[:50] if description else 'none'}")

        # Phase 4 (Claude Vision) + SightEngine run in parallel — both are I/O bound
        import asyncio
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=2) as executor:
            p4_future = loop.run_in_executor(executor, phase4_pixel_forensics, image_bytes, description)
            se_future = loop.run_in_executor(executor, call_sightengine, image_bytes)
            p4, se_result = await asyncio.gather(p4_future, se_future)

        logger.info(f"Phase 4 complete — pixel score: {p4['score']}, image_type: {p4['image_type']}, "
                    f"people: {p4.get('people_count', 0)}, contact_zones: {p4.get('contact_zones', 0)}")
        logger.info(f"SightEngine complete — se_score: {se_result.get('se_score')}, "
                    f"available: {se_result.get('available')}, conflict will be: se_vs_pipeline")

        # Use Claude's auto-description if user gave none
        effective_description = description or p4.get("auto_description", "")
        if not description and effective_description:
            logger.info(f"Auto-description from Phase 4: {effective_description[:80]}")

        p1 = phase1_context(source, effective_description, suspicion, claims)
        logger.info(f"Phase 1 complete — context score: {p1['score']}")

        p2 = phase2_reality(p1["search_queries"], effective_description, claims)
        logger.info(f"Phase 2 complete — reality score: {p2['score']}")

        p3 = phase3_reverse_search(effective_description)
        logger.info(f"Phase 3 complete — origin score: {p3['score']}")

        p6 = phase6_trend_viral(effective_description, claims)
        logger.info(f"Phase 6 complete — trend score: {p6['score']}")

        verdict = phase5_verdict(p1, p2, p3, p4, p6, se_result)
        logger.info(f"Phase 5 complete — pipeline: {verdict['pipeline_score']}, "
                    f"SE: {verdict['se_score']} (weight: {verdict['se_weight_used']}%), "
                    f"final: {verdict['final_score']}, verdict: {verdict['verdict']}, "
                    f"conflict: {verdict['se_conflict']}")

        summary = build_summary(verdict, p1, p2, p4, p6, source, description)

        return {
            "status":         "success",
            "verdict":        verdict["verdict"],
            "verdict_label":  verdict["verdict_label"],
            "ai_probability": verdict["final_score"],
            "confidence":     verdict["confidence"],
            "confidence_pct": verdict["confidence_pct"],
            "explanation":    summary,
            "sightengine": {
                "available":    se_result.get("available", False),
                "score":        se_result.get("se_score", 0),
                "confidence":   se_result.get("se_confidence", 0),
                "ai_generated": se_result.get("ai_generated", 0),
                "deepfake":     se_result.get("deepfake", 0),
                "weight_used":  verdict["se_weight_used"],
                "conflict":     verdict["se_conflict"],
            },
            "phase_details": {
                "phase1_context": {"score": p1["score"], "reasoning": p1["reasoning"]},
                "phase2_reality": {"score": p2["score"], "reasoning": p2["reasoning"], "findings": p2.get("findings", {})},
                "phase3_search":  {"score": p3["score"], "reasoning": p3["reasoning"]},
                "phase4_pixel":   {
                    "score":         p4["score"],
                    "image_type":    p4["image_type"],
                    "people_count":  p4.get("people_count", 0),
                    "contact_zones": p4.get("contact_zones", 0),
                    "level_scores":  p4["level_scores"],
                    "key_evidence":  p4["key_evidence"],
                },
                "phase6_trend":   {"score": p6["score"], "reasoning": p6["reasoning"]},
            },
            "verdict_engine": {
                "final_score":    verdict["final_score"],
                "pipeline_score": verdict["pipeline_score"],
                "se_score":       verdict["se_score"],
                "se_weight_used": verdict["se_weight_used"],
                "se_conflict":    verdict["se_conflict"],
                "phase_scores":   verdict["phase_scores"],
                "weights_used":   verdict["weights_used"],
                "conflicts":      verdict["conflicts"],
            },
            "filename": image.filename,
        }

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Intelligent detection error: {e!r}")
        raise HTTPException(status_code=502, detail=f"Detection failed: {e!r}")
