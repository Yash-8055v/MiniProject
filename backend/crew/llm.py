import os
from dotenv import load_dotenv

from crewai import LLM

# Load environment variables from .env
load_dotenv()

def get_llm():
    """
    Initialize and return the LLM instance using Groq.
    Using llama-3.3-70b-versatile via Groq for fast, free inference.
    """

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in .env file")

    # Set GROQ_API_KEY for litellm
    os.environ["GROQ_API_KEY"] = api_key

    llm = LLM(
        model="groq/llama-3.3-70b-versatile",
        api_key=api_key,
        temperature=0.2,
        max_tokens=1024
    )

    return llm
