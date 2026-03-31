"""
Media Verification Module — AI Image, Video & Audio Detection
Uses Hugging Face Inference API for deepfake/AI-generated content detection.
"""

import os
import logging
from io import BytesIO

from fastapi import APIRouter, UploadFile, File, HTTPException
from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Media Verification"])

# Temporary in-memory store for audio files served to Resemble Detect
_temp_audio_store: dict = {}  # { uuid: (bytes, content_type) }

# ---------------------------------------------------------------------------
# Hugging Face configuration
# ---------------------------------------------------------------------------
HF_MODEL = "prithivMLmods/Deep-Fake-Detector-v2-Model"
HF_AUDIO_MODEL = "MelodyMachine/Deepfake-audio-detection"

# Robust label sets — different models use different label names
_FAKE_LABELS = {"artificial", "fake", "ai_generated", "ai-generated", "generated", "deepfake", "manipulated", "spoof"}
_REAL_LABELS = {"real", "human", "bonafide", "genuine", "authentic", "natural"}

# Audio-specific label sets (ASVspoof convention: bonafide=real, spoof=fake)
_FAKE_AUDIO_LABELS = {"spoof", "fake", "ai", "generated", "artificial", "deepfake"}
_REAL_AUDIO_LABELS = {"bonafide", "real", "human", "genuine"}
MAX_IMAGE_SIZE = 1 * 1024 * 1024  # 1 MB threshold for internal compression
MAX_IMAGE_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB hard limit for uploads
MAX_VIDEO_UPLOAD_SIZE = 15 * 1024 * 1024  # 15 MB hard limit for videos


def _parse_ai_score(results) -> float:
    """
    Robustly extract AI/fake probability from HF classification results.
    Works across multiple models regardless of their label naming convention.
    Returns a float in [0.0, 1.0].
    """
    ai_score = 0.0
    real_score = 0.0
    for r in results:
        lbl = r.label.lower().replace("-", "_").replace(" ", "_")
        if lbl in _FAKE_LABELS or "fake" in lbl or "artificial" in lbl or "spoof" in lbl:
            ai_score = max(ai_score, r.score)
        elif lbl in _REAL_LABELS or "real" in lbl or "human" in lbl or "bonafide" in lbl:
            real_score = max(real_score, r.score)
    # If no fake label matched but a real label did, infer complement
    if ai_score == 0.0 and real_score > 0.0:
        ai_score = 1.0 - real_score
    return ai_score


def _get_hf_client() -> InferenceClient:
    """Create a Hugging Face InferenceClient using the API token from env."""
    token = os.getenv("HUGGING_FACE_API_TOKEN")
    if not token:
        raise RuntimeError("HUGGING_FACE_API_TOKEN is not set in environment")
    return InferenceClient(token=token)


# ---------------------------------------------------------------------------
# GET /api/temp-audio/{audio_id} — Serve temp audio for Resemble Detect
# ---------------------------------------------------------------------------
from fastapi.responses import Response

@router.get("/temp-audio/{audio_id}")
async def serve_temp_audio(audio_id: str):
    entry = _temp_audio_store.get(audio_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Audio not found or expired")
    audio_bytes, content_type = entry
    return Response(content=audio_bytes, media_type=content_type)


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

    # Validate size
    image.file.seek(0, os.SEEK_END)
    file_size = image.file.tell()
    image.file.seek(0)
    if file_size > MAX_IMAGE_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Image too large ({file_size / 1024 / 1024:.1f}MB). Max 5MB allowed.",
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
        logger.error(f"Hugging Face API error: {e!r}")
        raise HTTPException(
            status_code=502,
            detail=f"Hugging Face API request failed: {e!r}",
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

    # Extract AI probability — model-agnostic label parsing
    ai_probability = int(round(_parse_ai_score(results) * 100))

    # Determine verdict
    if ai_probability >= 70:
        verdict = "likely AI-generated"
    elif ai_probability >= 30:
        verdict = "uncertain"
    else:
        verdict = "likely real"

    # Generate explanation using Groq
    explanation = _get_ai_explanation(ai_probability, verdict, is_video=False)

    return {
        "status": "success",
        "ai_probability": ai_probability,
        "verdict": verdict,
        "filename": image.filename,
        "raw": raw_output,
        "explanation": explanation,
    }


# ---------------------------------------------------------------------------
# POST /api/detect-video — Video Analysis
# ---------------------------------------------------------------------------
@router.post("/detect-video")
async def detect_video(video: UploadFile = File(...)):
    """
    Accept an uploaded video, extract equidistant frames, analyze them with
    the Hugging Face AI-image-detector, and return aggregated probability.
    """
    if not video.content_type or not video.content_type.startswith("video/"):
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be a video (MP4, WEBM, MOV, etc.)",
        )

    # Validate size
    video.file.seek(0, os.SEEK_END)
    file_size = video.file.tell()
    video.file.seek(0)
    if file_size > MAX_VIDEO_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Video too large ({file_size / 1024 / 1024:.1f}MB). Max 15MB allowed.",
        )

    video_bytes = await video.read()
    if len(video_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded video is empty")

    import tempfile
    import cv2
    
    tmp_video_path = ""
    try:
        ext = os.path.splitext(video.filename)[1] if video.filename else ".mp4"
        if not ext:
            ext = ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(video_bytes)
            tmp_video_path = tmp.name

        frames = _extract_video_frames(tmp_video_path, num_frames=4)
        if not frames:
            raise HTTPException(status_code=400, detail="Could not extract frames from video.")
            
        client = _get_hf_client()
        total_ai_probability = 0
        valid_frames = 0
        
        for frame_bytes in frames:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_frame:
                tmp_frame.write(frame_bytes)
                tmp_frame_path = tmp_frame.name
                
            try:
                results = client.image_classification(
                    image=tmp_frame_path,
                    model=HF_MODEL,
                )
                
                total_ai_probability += int(round(_parse_ai_score(results) * 100))
                valid_frames += 1
            except Exception as e:
                logger.error(f"HF Error on video frame: {e}")
            finally:
                if os.path.exists(tmp_frame_path):
                    os.remove(tmp_frame_path)
                    
        if valid_frames == 0:
            raise HTTPException(status_code=502, detail="Failed to analyze video frames via HF API.")
            
        avg_ai_probability = int(total_ai_probability / valid_frames)
        
        if avg_ai_probability >= 60:
            verdict = "likely AI-generated"
        elif avg_ai_probability >= 30:
            verdict = "uncertain"
        else:
            verdict = "likely real"

        image_bytes_for_explanation = frames[len(frames) // 2] if frames else None
        explanation = _get_ai_explanation(avg_ai_probability, verdict, is_video=True)
        
        return {
            "status": "success",
            "ai_probability": avg_ai_probability,
            "verdict": verdict,
            "filename": video.filename,
            "raw": [{"label": "Deepfake", "score": avg_ai_probability / 100}],
            "explanation": explanation,
            "frames_analyzed": valid_frames
        }

    finally:
        if tmp_video_path and os.path.exists(tmp_video_path):
            os.remove(tmp_video_path)


def _get_ai_explanation(ai_probability: int, verdict: str, is_video: bool = False) -> dict:
    import json
    import requests

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {
            "english": "Explanation not available.",
            "hindi": "स्पष्टीकरण उपलब्ध नहीं है।",
            "marathi": "स्पष्टीकरण उपलब्ध नाही."
        }

    media_type = "video" if is_video else "image"
    prompt = (
        f"An AI {media_type} detection tool analyzed a {media_type} and gave it a {ai_probability}% probability "
        f"of being AI-generated. The final verdict is '{verdict}'.\n\n"
        f"Write a simple 1-2 sentence explanation in English, Hindi, and Marathi for a non-technical user, explaining "
        f"why a {media_type} might get this score (e.g. if it's likely AI, mention common artifacts like unnatural lighting or perfect symmetry. If likely real, mention natural imperfections).\n\n"
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

def _extract_video_frames(video_path: str, num_frames: int = 4) -> list[bytes]:
    """
    Extract perfectly spaced frames from a video file and return their compressed JPEG bytes.
    """
    import cv2
    from PIL import Image
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        total_frames = 1
        
    step = max(1, total_frames // num_frames)
    frame_bytes_list = []
    
    for i in range(num_frames):
        frame_idx = i * step
        if frame_idx >= total_frames:
            frame_idx = total_frames - 1
            
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            continue
            
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        try:
            pil_img = Image.fromarray(frame_rgb)
            img_byte_arr = BytesIO()
            pil_img.save(img_byte_arr, format='JPEG', quality=85)
            img_bytes = img_byte_arr.getvalue()
            final_bytes = _compress_image(img_bytes, MAX_IMAGE_SIZE)
            frame_bytes_list.append(final_bytes)
        except Exception as e:
            logger.error(f"Frame extraction error: {e}")
            
    cap.release()
    return frame_bytes_list


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


def _parse_audio_ai_score(results) -> float:
    """Robustly extract fake/spoof probability from HF audio classification results."""
    ai_score = 0.0
    real_score = 0.0
    for r in results:
        lbl = r.label.lower().replace("-", "_").replace(" ", "_")
        if lbl in _FAKE_AUDIO_LABELS or "fake" in lbl or "spoof" in lbl:
            ai_score = max(ai_score, r.score)
        elif lbl in _REAL_AUDIO_LABELS or "real" in lbl or "bonafide" in lbl:
            real_score = max(real_score, r.score)
    if ai_score == 0.0 and real_score > 0.0:
        ai_score = 1.0 - real_score
    return ai_score


# ---------------------------------------------------------------------------
# POST /api/detect-audio — Audio Deepfake Detection
# ---------------------------------------------------------------------------
MAX_AUDIO_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/detect-audio")
async def detect_audio(audio: UploadFile = File(...)):
    """
    Accept an uploaded audio file and detect whether it is AI-generated (deepfake).
    Uses MelodyMachine/Deepfake-audio-detection-V2 via HuggingFace Inference API.
    """
    import tempfile

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
            detail=f"Audio too large ({file_size / 1024 / 1024:.1f}MB). Max 10MB allowed.",
        )

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty")

    # Determine file suffix from content-type
    ct = audio.content_type or "audio/webm"
    suffix_map = {
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/ogg": ".ogg",
        "audio/webm": ".webm",
    }
    suffix = suffix_map.get(ct, ".webm")

    import httpx

    # Audio deepfake detection via dedicated API — returns graceful unavailable response
    return {
        "status": "unavailable",
        "ai_probability": 0,
        "verdict": "unavailable",
        "filename": audio.filename,
        "raw": [],
        "explanation": {
            "english": "Audio deepfake detection requires dedicated GPU infrastructure. This feature is planned for the next release.",
            "hindi": "ऑडियो डीपफेक डिटेक्शन के लिए समर्पित GPU इन्फ्रास्ट्रक्चर की आवश्यकता है। यह सुविधा अगले संस्करण में उपलब्ध होगी।",
            "marathi": "ऑडिओ डीपफेक डिटेक्शनसाठी समर्पित GPU इन्फ्रास्ट्रक्चर आवश्यक आहे. ही सुविधा पुढील आवृत्तीत उपलब्ध होईल."
        },
    }


    # REST API returns plain dicts: [{"label": "...", "score": ...}]
    raw_output = [{"label": r["label"], "score": round(r["score"], 4)} for r in results]

    # Convert to simple namespace objects for _parse_audio_ai_score compatibility
    class _R:
        def __init__(self, d): self.label = d["label"]; self.score = d["score"]
    ai_probability = int(round(_parse_audio_ai_score([_R(r) for r in results]) * 100))

    if ai_probability >= 70:
        verdict = "likely AI-generated voice"
    elif ai_probability >= 30:
        verdict = "uncertain"
    else:
        verdict = "likely real voice"

    explanation = _get_ai_explanation(ai_probability, verdict, is_video=False)

    return {
        "status": "success",
        "ai_probability": ai_probability,
        "verdict": verdict,
        "filename": audio.filename,
        "raw": raw_output,
        "explanation": explanation,
    }
