"""
Media Verification Module — AI Image & Video Detection
Uses Hugging Face Inference API with Organika/sdxl-detector model.
"""

import os
import logging
from io import BytesIO

from fastapi import APIRouter, UploadFile, File, HTTPException
from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Media Verification"])

# ---------------------------------------------------------------------------
# Hugging Face configuration
# ---------------------------------------------------------------------------
HF_MODEL = "Organika/sdxl-detector"
MAX_IMAGE_SIZE = 1 * 1024 * 1024  # 1 MB limit for free HF Inference API


def _get_hf_client() -> InferenceClient:
    """Create a Hugging Face InferenceClient using the API token from env."""
    token = os.getenv("HUGGING_FACE_API_TOKEN")
    if not token:
        raise RuntimeError("HUGGING_FACE_API_TOKEN is not set in environment")
    return InferenceClient(token=token)


# ---------------------------------------------------------------------------
# POST /api/detect-image — Phase 1: raw model output
# ---------------------------------------------------------------------------
@router.post("/detect-image")
async def detect_image(image: UploadFile = File(...)):
    """
    Accept an uploaded image and send it to the Hugging Face
    AI-image-detector model. Returns the raw model output.
    """
    # Validate content type
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be an image (JPEG, PNG, WebP, etc.)",
        )

    # Read image bytes
    image_bytes = await image.read()

    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")

    # Resize if too large for the free HF API
    if len(image_bytes) > MAX_IMAGE_SIZE:
        image_bytes = _compress_image(image_bytes)

    import tempfile
    
    # Send to Hugging Face
    tmp_path = ""
    try:
        # Write bytes to a temporary file (InferenceClient handles local files perfectly)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        client = _get_hf_client()
        results = client.image_classification(
            image=tmp_path,
            model=HF_MODEL,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Hugging Face API error: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Hugging Face API request failed: {str(e)}",
        )
    finally:
        # Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Collect raw output
    raw_output = [
        {"label": r.label, "score": round(r.score, 4)}
        for r in results
    ]

    # Extract AI probability
    ai_score = 0.0
    for r in results:
        # Looking for 'artificial' label which is used by Organika/sdxl-detector
        if r.label.lower() == "artificial":
            ai_score = r.score
    
    ai_probability = int(round(ai_score * 100))

    # Determine verdict
    if ai_probability >= 70:
        verdict = "likely AI-generated"
    elif ai_probability >= 30:
        verdict = "uncertain"
    else:
        verdict = "likely real"

    # Generate explanation using Groq
    explanation = _get_ai_explanation(ai_probability, verdict)

    return {
        "status": "success",
        "ai_probability": ai_probability,
        "verdict": verdict,
        "filename": image.filename,
        "raw": raw_output,
        "explanation": explanation,
    }

def _get_ai_explanation(ai_probability: int, verdict: str) -> dict:
    import json
    import requests

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {
            "english": "Explanation not available.",
            "hindi": "स्पष्टीकरण उपलब्ध नहीं है।",
            "marathi": "स्पष्टीकरण उपलब्ध नाही."
        }

    prompt = (
        f"An AI image detection tool analyzed an image and gave it a {ai_probability}% probability "
        f"of being AI-generated. The final verdict is '{verdict}'.\n\n"
        f"Write a simple 1-2 sentence explanation in English, Hindi, and Marathi for a non-technical user, explaining "
        f"why an image might get this score (e.g. if it's likely AI, mention common artifacts like unnatural lighting or perfect symmetry. If likely real, mention natural imperfections).\n\n"
        f"Return ONLY a valid JSON object with keys 'english', 'hindi', and 'marathi'."
    )

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "response_format": {"type": "json_object"}
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=15,
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"].strip()
        data = json.loads(content)
        return {
            "english": data.get("english", ""),
            "hindi": data.get("hindi", ""),
            "marathi": data.get("marathi", "")
        }
    except Exception as e:
        logger.error(f"Explanation generation failed: {e}")
        return {
            "english": "Explanation not available due to an error.",
            "hindi": "त्रुटीमुळे स्पष्टीकरण उपलब्ध नहीं है।",
            "marathi": "त्रुटीमुळे स्पष्टीकरण उपलब्ध नाही."
        }


def _compress_image(image_bytes: bytes, max_size: int = MAX_IMAGE_SIZE) -> bytes:
    """
    Compress/resize an image to fit within the HF API size limit.
    Preserves as much quality as possible.
    """
    from PIL import Image

    img = Image.open(BytesIO(image_bytes))

    # Convert RGBA to RGB if needed (JPEG doesn't support alpha)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    quality = 90
    while quality >= 40:
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        if buffer.tell() <= max_size:
            buffer.seek(0)
            return buffer.read()
        quality -= 10

    # If still too large, resize dimensions
    width, height = img.size
    while width > 256 or height > 256:
        width = int(width * 0.75)
        height = int(height * 0.75)
        resized = img.resize((width, height), Image.LANCZOS)
        buffer = BytesIO()
        resized.save(buffer, format="JPEG", quality=80)
        if buffer.tell() <= max_size:
            buffer.seek(0)
            return buffer.read()

    # Last resort
    buffer = BytesIO()
    img.resize((512, 512), Image.LANCZOS).save(buffer, format="JPEG", quality=60)
    buffer.seek(0)
    return buffer.read()
