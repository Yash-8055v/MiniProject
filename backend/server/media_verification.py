"""
Media Verification Module — AI Image, Video & Audio Detection
Uses Groq Vision (LLaMA multimodal) for AI-generated content detection.
Groq Vision reasons about images holistically — lighting, texture, geometry,
and stylistic artifacts — rather than relying on a fixed classification head.
"""

import os
import base64
import json
import logging
import re
import requests
from io import BytesIO

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Media Verification"])

MAX_IMAGE_SIZE = 1 * 1024 * 1024        # 1 MB threshold for internal compression
MAX_IMAGE_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB hard limit for uploads
MAX_VIDEO_UPLOAD_SIZE = 15 * 1024 * 1024  # 15 MB hard limit for videos
MAX_AUDIO_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB hard limit for audio

GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


# ---------------------------------------------------------------------------
# Core: Groq Vision analysis
# ---------------------------------------------------------------------------

def _analyze_with_groq_vision(image_bytes: bytes, context: str = "image") -> dict:
    """
    Send an image to Groq Vision (LLaMA multimodal) and ask it to determine
    whether the image is AI-generated or a real photograph.

    Returns:
        {
            "ai_probability": int (0-100),
            "verdict": str,
            "explanation": { "english": str, "hindi": str, "marathi": str }
        }
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set in environment")

    # Compress if needed before base64 encoding
    if len(image_bytes) > MAX_IMAGE_SIZE:
        image_bytes = _compress_image(image_bytes)

    b64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = (
        f"You are an expert forensic image analyst. Examine this {context} carefully.\n\n"
        "Determine whether it is AI-generated or a real photograph/recording.\n\n"
        "Look for these AI-generation indicators:\n"
        "- Unnatural, impossible, or inconsistent lighting and shadows\n"
        "- Overly smooth, plastic, or airbrushed skin/textures\n"
        "- Distorted fingers, hands, ears, teeth, or text\n"
        "- Perfect symmetry that does not occur naturally\n"
        "- Incoherent or merged background elements\n"
        "- Painterly, hyper-vivid, or fantasy art style\n"
        "- Watermarks or style artifacts from Midjourney, DALL-E, Stable Diffusion\n"
        "- Impossible geometry or physics\n\n"
        "Real photographs typically have:\n"
        "- Natural imperfections, grain, motion blur\n"
        "- Consistent perspective and lighting\n"
        "- Normal compression artifacts from cameras/phones\n\n"
        "Respond ONLY with a valid JSON object:\n"
        "{\n"
        '  "ai_probability": <integer 0-100>,\n'
        '  "english": "<1-2 sentence explanation for a non-technical user>",\n'
        '  "hindi": "<same explanation in Hindi>",\n'
        '  "marathi": "<same explanation in Marathi>"\n'
        "}\n\n"
        "ai_probability: 0 = definitely real photograph, 100 = definitely AI-generated."
    )

    payload = {
        "model": GROQ_VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "temperature": 0.1,
        "max_tokens": 500,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()

    raw_content = resp.json()["choices"][0]["message"]["content"].strip()

    # Extract JSON robustly
    data = _extract_json(raw_content)

    ai_probability = max(0, min(100, int(data.get("ai_probability", 50))))

    if ai_probability >= 70:
        verdict = "likely AI-generated"
    elif ai_probability >= 35:
        verdict = "uncertain"
    else:
        verdict = "likely real"

    return {
        "ai_probability": ai_probability,
        "verdict": verdict,
        "explanation": {
            "english": data.get("english", "Analysis complete."),
            "hindi": data.get("hindi", "विश्लेषण पूर्ण।"),
            "marathi": data.get("marathi", "विश्लेषण पूर्ण."),
        },
    }


def _extract_json(text: str) -> dict:
    """Robustly extract a JSON object from LLM output."""
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Brace-depth matching
    start = cleaned.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cleaned[start : i + 1])
                    except json.JSONDecodeError:
                        break

    # Regex fallback for individual fields
    prob_match = re.search(r'"ai_probability"\s*:\s*(\d+)', cleaned)
    en_match = re.search(r'"english"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    hi_match = re.search(r'"hindi"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    mr_match = re.search(r'"marathi"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)

    return {
        "ai_probability": int(prob_match.group(1)) if prob_match else 50,
        "english": en_match.group(1) if en_match else "",
        "hindi": hi_match.group(1) if hi_match else "",
        "marathi": mr_match.group(1) if mr_match else "",
    }


# ---------------------------------------------------------------------------
# POST /api/detect-image
# ---------------------------------------------------------------------------

@router.post("/detect-image")
async def detect_image(image: UploadFile = File(...)):
    """
    Accept an uploaded image and use Groq Vision (LLaMA multimodal) to
    determine whether it is AI-generated or a real photograph.
    """
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be an image (JPEG, PNG, WebP, etc.)",
        )

    image.file.seek(0, os.SEEK_END)
    file_size = image.file.tell()
    image.file.seek(0)
    if file_size > MAX_IMAGE_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Image too large ({file_size / 1024 / 1024:.1f} MB). Max 5 MB allowed.",
        )

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    try:
        result = _analyze_with_groq_vision(image_bytes, context="image")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Groq Vision error (image): {e!r}")
        raise HTTPException(status_code=502, detail=f"Vision analysis failed: {e!r}")

    return {
        "status": "success",
        "ai_probability": result["ai_probability"],
        "verdict": result["verdict"],
        "filename": image.filename,
        "raw": [{"label": "AI-Generated", "score": result["ai_probability"] / 100}],
        "explanation": result["explanation"],
    }


# ---------------------------------------------------------------------------
# POST /api/detect-video
# ---------------------------------------------------------------------------

@router.post("/detect-video")
async def detect_video(video: UploadFile = File(...)):
    """
    Accept an uploaded video, extract 2 representative frames, analyze each
    with Groq Vision, and return the averaged AI probability.
    """
    if not video.content_type or not video.content_type.startswith("video/"):
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be a video (MP4, WEBM, MOV, etc.)",
        )

    video.file.seek(0, os.SEEK_END)
    file_size = video.file.tell()
    video.file.seek(0)
    if file_size > MAX_VIDEO_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Video too large ({file_size / 1024 / 1024:.1f} MB). Max 15 MB allowed.",
        )

    video_bytes = await video.read()
    if not video_bytes:
        raise HTTPException(status_code=400, detail="Uploaded video is empty.")

    import tempfile

    tmp_video_path = ""
    try:
        ext = (os.path.splitext(video.filename)[1] if video.filename else "") or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(video_bytes)
            tmp_video_path = tmp.name

        # Extract 3 frames (start, middle, end) — analyze 2 to save tokens
        frames = _extract_video_frames(tmp_video_path, num_frames=3)
        if not frames:
            raise HTTPException(status_code=400, detail="Could not extract frames from video.")

        # Analyze first and middle frame
        frames_to_analyze = [frames[0], frames[len(frames) // 2]]
        total_prob = 0
        valid = 0
        last_explanation = None

        for frame_bytes in frames_to_analyze:
            try:
                res = _analyze_with_groq_vision(frame_bytes, context="video frame")
                total_prob += res["ai_probability"]
                valid += 1
                last_explanation = res["explanation"]
            except Exception as e:
                logger.error(f"Groq Vision error on video frame: {e}")

        if valid == 0:
            raise HTTPException(status_code=502, detail="Failed to analyze video frames.")

        avg_prob = int(total_prob / valid)

        if avg_prob >= 70:
            verdict = "likely AI-generated"
        elif avg_prob >= 35:
            verdict = "uncertain"
        else:
            verdict = "likely real"

        return {
            "status": "success",
            "ai_probability": avg_prob,
            "verdict": verdict,
            "filename": video.filename,
            "raw": [{"label": "AI-Generated", "score": avg_prob / 100}],
            "explanation": last_explanation,
            "frames_analyzed": valid,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video detection error: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_video_path and os.path.exists(tmp_video_path):
            os.remove(tmp_video_path)


# ---------------------------------------------------------------------------
# POST /api/detect-audio — Coming Soon
# ---------------------------------------------------------------------------

@router.post("/detect-audio")
async def detect_audio(audio: UploadFile = File(...)):
    """Audio deepfake detection — planned for next release."""
    if not audio.content_type or not audio.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be an audio file (MP3, WAV, OGG, WEBM, etc.)",
        )

    audio.file.seek(0, os.SEEK_END)
    file_size = audio.file.tell()
    audio.file.seek(0)
    if file_size > MAX_AUDIO_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Audio too large ({file_size / 1024 / 1024:.1f} MB). Max 10 MB allowed.",
        )

    return {
        "status": "unavailable",
        "ai_probability": 0,
        "verdict": "unavailable",
        "filename": audio.filename,
        "raw": [],
        "explanation": {
            "english": "Audio deepfake detection requires dedicated GPU infrastructure. This feature is planned for the next release.",
            "hindi": "ऑडियो डीपफेक डिटेक्शन के लिए समर्पित GPU इन्फ्रास्ट्रक्चर की आवश्यकता है। यह सुविधा अगले संस्करण में उपलब्ध होगी।",
            "marathi": "ऑडिओ डीपफेक डिटेक्शनसाठी समर्पित GPU इन्फ्रास्ट्रक्चर आवश्यक आहे. ही सुविधा पुढील आवृत्तीत उपलब्ध होईल.",
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_video_frames(video_path: str, num_frames: int = 3) -> list[bytes]:
    """Extract evenly-spaced frames from a video and return JPEG bytes."""
    import cv2
    from PIL import Image

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    step = max(1, total_frames // num_frames)
    frame_bytes_list = []

    for i in range(num_frames):
        frame_idx = min(i * step, total_frames - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            continue
        try:
            pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            buf = BytesIO()
            pil_img.save(buf, format="JPEG", quality=85)
            frame_bytes_list.append(_compress_image(buf.getvalue()))
        except Exception as e:
            logger.error(f"Frame extraction error: {e}")

    cap.release()
    return frame_bytes_list


def _compress_image(image_bytes: bytes, max_size: int = MAX_IMAGE_SIZE) -> bytes:
    """Compress/resize an image to fit within the size limit."""
    from PIL import Image

    img = Image.open(BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    quality = 90
    while quality >= 40:
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= max_size:
            buf.seek(0)
            return buf.read()
        quality -= 10

    # Resize if still too large
    w, h = img.size
    while w > 256 or h > 256:
        w, h = int(w * 0.75), int(h * 0.75)
        resized = img.resize((w, h), Image.LANCZOS)
        buf = BytesIO()
        resized.save(buf, format="JPEG", quality=80)
        if buf.tell() <= max_size:
            buf.seek(0)
            return buf.read()

    buf = BytesIO()
    img.resize((512, 512), Image.LANCZOS).save(buf, format="JPEG", quality=60)
    buf.seek(0)
    return buf.read()
