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
MAX_IMAGE_SIZE = 1 * 1024 * 1024  # 1 MB threshold for internal compression
MAX_IMAGE_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB hard limit for uploads
MAX_VIDEO_UPLOAD_SIZE = 15 * 1024 * 1024  # 15 MB hard limit for videos


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
                
                ai_score = 0.0
                for r in results:
                    if r.label.lower() == "artificial":
                        ai_score = r.score
                total_ai_probability += int(round(ai_score * 100))
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
            "raw": [{"label": "artificial", "score": avg_ai_probability / 100}],
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
