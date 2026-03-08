import os
import requests
from dotenv import load_dotenv

load_dotenv()

SERP_API_KEY = os.getenv("SEARCH_API_KEY")


def web_search(query: str, num_results: int = 5):
    """
    Perform a web search using SerpAPI and return simplified results.
    """

    if not SERP_API_KEY:
        raise ValueError("SEARCH_API_KEY not found in .env")

    params = {
        "q": query,
        "api_key": SERP_API_KEY,
        "engine": "google",
        "num": num_results
    }

    response = requests.get("https://serpapi.com/search", params=params, timeout=10)
    response.raise_for_status()

    data = response.json()

    results = []

    for item in data.get("organic_results", []):
        results.append({
            "title": item.get("title"),
            "snippet": item.get("snippet"),
            "source": item.get("source", item.get("link"))
        })

    return results
