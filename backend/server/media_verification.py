"""
Media Verification Module — AI Image, Video & Deepfake Detection
Uses SightEngine API — purpose-built models for:
  - AI-generated image detection (MidJourney, DALL-E, Stable Diffusion, FLUX, etc.)
  - Deepfake detection (face swaps, face manipulation in real photos/videos)
"""

import os
import logging
import tempfile
import requests

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response
from io import BytesIO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Media Verification"])

MAX_IMAGE_UPLOAD_SIZE = 20 * 1024 * 1024   # 20 MB
MAX_VIDEO_UPLOAD_SIZE = 15 * 1024 * 1024   # 15 MB
MAX_AUDIO_UPLOAD_SIZE = 10 * 1024 * 1024   # 10 MB

SIGHTENGINE_URL = "https://api.sightengine.com/1.0/check.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_credentials():
    api_user   = os.getenv("SIGHTENGINE_API_USER")
    api_secret = os.getenv("SIGHTENGINE_API_SECRET")
    if not api_user or not api_secret:
        raise RuntimeError("SIGHTENGINE_API_USER or SIGHTENGINE_API_SECRET not set in environment")
    return api_user, api_secret


def _build_explanation(ai_score: float, deepfake_score: float, verdict: str) -> dict:
    """Build trilingual explanation based on scores."""
    ai_pct      = int(ai_score * 100)
    fake_pct    = int(deepfake_score * 100)

    if verdict == "likely AI-generated":
        english = (
            f"This media has a {ai_pct}% probability of being AI-generated. "
            "Visual analysis detected patterns consistent with AI image generators "
            "such as MidJourney, DALL-E, Stable Diffusion, or FLUX."
        )
        hindi = (
            f"इस मीडिया के AI-जनित होने की {ai_pct}% संभावना है। "
            "दृश्य विश्लेषण में MidJourney, DALL-E या Stable Diffusion जैसे "
            "AI इमेज जनरेटर के पैटर्न पाए गए।"
        )
        marathi = (
            f"या मीडियाची AI-निर्मित असण्याची {ai_pct}% शक्यता आहे। "
            "दृश्य विश्लेषणात MidJourney, DALL-E किंवा Stable Diffusion सारख्या "
            "AI इमेज जनरेटरचे नमुने आढळले."
        )
    elif verdict == "likely deepfake":
        english = (
            f"This media has a {fake_pct}% probability of being a deepfake. "
            "Facial analysis detected signs of face swapping or AI-based "
            "facial manipulation."
        )
        hindi = (
            f"इस मीडिया के डीपफेक होने की {fake_pct}% संभावना है। "
            "चेहरे के विश्लेषण में फेस स्वैपिंग या AI-आधारित चेहरे की "
            "हेरफेर के संकेत मिले।"
        )
        marathi = (
            f"या मीडियाची डीपफेक असण्याची {fake_pct}% शक्यता आहे। "
            "चेहऱ्याच्या विश्लेषणात फेस स्वॅपिंग किंवा AI-आधारित "
            "चेहऱ्याच्या फेरफाराची चिन्हे आढळली."
        )
    elif verdict == "uncertain":
        english = (
            f"This media shows mixed signals — {ai_pct}% AI-generation probability "
            f"and {fake_pct}% deepfake probability. It may be partially manipulated "
            "or heavily edited. Treat with caution."
        )
        hindi = (
            f"इस मीडिया में मिश्रित संकेत हैं — {ai_pct}% AI-जनित संभावना "
            f"और {fake_pct}% डीपफेक संभावना। यह आंशिक रूप से हेरफेर किया गया हो सकता है।"
        )
        marathi = (
            f"या मीडियामध्ये मिश्र संकेत आहेत — {ai_pct}% AI-निर्मित शक्यता "
            f"आणि {fake_pct}% डीपफेक शक्यता. हे अंशतः फेरफार केलेले असू शकते."
        )
    else:
        english = (
            f"This media appears to be authentic. AI-generation probability: {ai_pct}%, "
            f"deepfake probability: {fake_pct}%. No significant signs of manipulation detected."
        )
        hindi = (
            f"यह मीडिया प्रामाणिक प्रतीत होती है। AI-जनित संभावना: {ai_pct}%, "
            f"डीपफेक संभावना: {fake_pct}%। कोई महत्वपूर्ण हेरफेर नहीं पाई गई।"
        )
        marathi = (
            f"हे मीडिया प्रामाणिक वाटते. AI-निर्मित शक्यता: {ai_pct}%, "
            f"डीपफेक शक्यता: {fake_pct}%. कोणताही महत्त्वाचा फेरफार आढळला नाही."
        )

    return {"english": english, "hindi": hindi, "marathi": marathi}


def _score_to_verdict(ai_score: float, deepfake_score: float) -> tuple[str, int]:
    """
    Determine verdict and combined probability from SightEngine scores.
    Returns (verdict, ai_probability_0_to_100)
    """
    combined = max(ai_score, deepfake_score)
    ai_probability = int(combined * 100)

    if deepfake_score >= 0.70:
        verdict = "likely deepfake"
    elif ai_score >= 0.70:
        verdict = "likely AI-generated"
    elif combined >= 0.35:
        verdict = "uncertain"
    else:
        verdict = "likely real"

    return verdict, ai_probability


# ---------------------------------------------------------------------------
# Core: SightEngine image analysis
# ---------------------------------------------------------------------------

def _analyze_image_with_sightengine(image_bytes: bytes, filename: str = "") -> dict:
    """
    Send image bytes to SightEngine and get AI-generation + deepfake scores.
    Returns:
        {
            "ai_probability": int (0-100),
            "verdict": str,
            "explanation": { "english": str, "hindi": str, "marathi": str }
        }
    """
    api_user, api_secret = _get_credentials()

    files   = {"media": (filename or "image.jpg", image_bytes, "image/jpeg")}
    payload = {
        "models":     "genai,deepfake",
        "api_user":   api_user,
        "api_secret": api_secret,
    }

    resp = requests.post(SIGHTENGINE_URL, files=files, data=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "success":
        raise RuntimeError(f"SightEngine error: {data.get('error', {}).get('message', 'Unknown error')}")

    ai_score       = float(data.get("type", {}).get("ai_generated", 0))
    deepfake_score = float(data.get("type", {}).get("deepfake", 0))

    verdict, ai_probability = _score_to_verdict(ai_score, deepfake_score)
    explanation = _build_explanation(ai_score, deepfake_score, verdict)

    return {
        "ai_probability": ai_probability,
        "verdict":        verdict,
        "explanation":    explanation,
    }


# ---------------------------------------------------------------------------
# POST /api/detect-image
# ---------------------------------------------------------------------------

@router.post(
    "/detect-image",
    tags=["🖼️ Media Verification"],
    summary="Detect AI-generated images using Groq Vision",
    response_description="AI probability score (0-100), verdict, and multilingual explanation",
)
async def detect_image(
    image: UploadFile = File(
        ...,
        description="Image file to analyze (JPEG, PNG, WebP). Max 20 MB.",
    ),
):
    """
    Accept an uploaded image and use SightEngine to determine whether it is
    AI-generated or contains deepfake facial manipulation.
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
            detail=f"Image too large ({file_size / 1024 / 1024:.1f} MB). Max 20 MB allowed.",
        )

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    try:
        result = _analyze_image_with_sightengine(image_bytes, filename=image.filename or "image.jpg")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"SightEngine error (image): {e!r}")
        raise HTTPException(status_code=502, detail=f"Image analysis failed: {e!r}")

    return {
        "status":         "success",
        "ai_probability": result["ai_probability"],
        "verdict":        result["verdict"],
        "filename":       image.filename,
        "raw":            [{"label": "AI-Generated", "score": result["ai_probability"] / 100}],
        "explanation":    result["explanation"],
    }


# ---------------------------------------------------------------------------
# POST /api/detect-video
# ---------------------------------------------------------------------------

@router.post(
    "/detect-video",
    tags=["🖼️ Media Verification"],
    summary="Detect AI-generated videos using frame analysis",
    response_description="Averaged AI probability from 2 analyzed frames, verdict, and explanation",
)
async def detect_video(
    video: UploadFile = File(
        ...,
        description="Video file to analyze (MP4, WEBM, MOV). Max 15 MB.",
    ),
):
    """
    Accept an uploaded video, extract 3 representative frames, analyze each
    with SightEngine, and return the averaged AI probability.
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

    tmp_video_path = ""
    try:
        ext = (os.path.splitext(video.filename)[1] if video.filename else "") or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(video_bytes)
            tmp_video_path = tmp.name

        frames = _extract_video_frames(tmp_video_path, num_frames=3)
        if not frames:
            raise HTTPException(status_code=400, detail="Could not extract frames from video.")

        total_prob     = 0
        valid          = 0
        last_explanation = None

        for frame_bytes in frames:
            try:
                res = _analyze_image_with_sightengine(frame_bytes, filename="frame.jpg")
                total_prob      += res["ai_probability"]
                valid           += 1
                last_explanation = res["explanation"]
            except Exception as e:
                logger.error(f"SightEngine error on video frame: {e}")

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
            "status":          "success",
            "ai_probability":  avg_prob,
            "verdict":         verdict,
            "filename":        video.filename,
            "raw":             [{"label": "AI-Generated", "score": avg_prob / 100}],
            "explanation":     last_explanation,
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

@router.post(
    "/detect-audio",
    tags=["🖼️ Media Verification"],
    summary="Audio deepfake detection (coming soon)",
    response_description="Placeholder response — feature requires dedicated GPU infrastructure",
)
async def detect_audio(
    audio: UploadFile = File(
        ...,
        description="Audio file to analyze (MP3, WAV, OGG, WEBM). Max 10 MB.",
    ),
):
    """
    ## Audio Deepfake Detection (Planned)

    ⚠️ **This feature is currently unavailable.**

    Audio deepfake detection requires dedicated GPU infrastructure that is not
    available on the current free-tier hosting. This endpoint validates the upload
    and returns a placeholder response.

    ### Planned Implementation
    - Resemble AI Detect API for voice clone detection
    - Spectral analysis for synthetic speech artifacts
    """
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
        "status":         "unavailable",
        "ai_probability": 0,
        "verdict":        "unavailable",
        "filename":       audio.filename,
        "raw":            [],
        "explanation": {
            "english": "Audio deepfake detection requires dedicated infrastructure. This feature is planned for the next release.",
            "hindi":   "ऑडियो डीपफेक डिटेक्शन के लिए समर्पित इन्फ्रास्ट्रक्चर की आवश्यकता है। यह सुविधा अगले संस्करण में उपलब्ध होगी।",
            "marathi": "ऑडिओ डीपफेक डिटेक्शनसाठी समर्पित इन्फ्रास्ट्रक्चर आवश्यक आहे. ही सुविधा पुढील आवृत्तीत उपलब्ध होईल.",
        },
    }


# ---------------------------------------------------------------------------
# Helpers — Video frame extraction
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
            frame_bytes_list.append(buf.getvalue())
        except Exception as e:
            logger.error(f"Frame extraction error: {e}")

    cap.release()
    return frame_bytes_list
