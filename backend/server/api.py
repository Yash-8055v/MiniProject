from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from crew.crew import run_crew

app = FastAPI(title="Fake News Verification API")

# Allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/verify")
async def verify_news(
    text: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None)
):
    """
    Accepts:
    - text (optional)
    - image (optional)

    Returns:
    - Verification result in English, Hindi, and Marathi
    """

    # Normalize text
    if text:
        text = text.strip()

    if not text and not image:
        raise HTTPException(
            status_code=400,
            detail="Either non-empty text or image must be provided"
        )

    # Safely read image if provided (future use)
    image_bytes = None
    if image:
        image_bytes = await image.read()

    crew_input = {
        "text": text,
        "image_provided": bool(image_bytes),
        # "image_bytes": image_bytes  # keep commented until implemented
    }

    try:
        result = run_crew(crew_input)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


    return {
        "status": "success",
        "languages": ["en", "hi", "mr"],
        "data": result
    }
