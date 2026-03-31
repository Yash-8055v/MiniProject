from pathlib import Path
import yaml
import json
import re

from crewai import Agent, Task, Crew, Process
import litellm

from crew.llm import get_llm
from tools.web_search import search_with_priority
from server.credibility_scorer import calculate_credibility_score


# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"


def load_yaml(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_result(raw_output: str) -> dict:
    """
    Parse the final agent output into a structured dict.
    Tries multiple strategies to extract JSON from LLM output.
    """

    # Strategy 1: Strip markdown code fences and try direct json.loads
    cleaned = re.sub(r'```(?:json)?\s*', '', raw_output)
    cleaned = cleaned.strip()

    # Try direct parse of cleaned text
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: Brace-depth matching to find outermost JSON object
    brace_start = cleaned.find('{')
    if brace_start != -1:
        depth = 0
        for i in range(brace_start, len(cleaned)):
            if cleaned[i] == '{':
                depth += 1
            elif cleaned[i] == '}':
                depth -= 1
                if depth == 0:
                    json_str = cleaned[brace_start:i + 1]
                    try:
                        result = json.loads(json_str)
                        return result
                    except json.JSONDecodeError:
                        break

    # Strategy 3: Regex extraction of individual fields
    verdict_match = re.search(r'"verdict"\s*:\s*"([^"]*)"', cleaned)
    confidence_match = re.search(r'"confidence"\s*:\s*(\d+)', cleaned)
    english_match = re.search(r'"english"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    hindi_match = re.search(r'"hindi"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    marathi_match = re.search(r'"marathi"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)

    if verdict_match and english_match:
        result = {
            "verdict": verdict_match.group(1),
            "confidence": int(confidence_match.group(1)) if confidence_match else 0,
            "english": english_match.group(1),
            "hindi": hindi_match.group(1) if hindi_match else "",
            "marathi": marathi_match.group(1) if marathi_match else ""
        }
        return result

    return {
        "verdict": "Unknown",
        "confidence": 0,
        "english": raw_output,
        "hindi": "",
        "marathi": ""
    }


def translate_claim_to_english(claim: str, llm_instance) -> str:
    """
    Translate claim to English if it's in Hindi, Marathi, Hinglish, etc.
    Uses a single lightweight LLM call. Returns original if already English.
    """
    try:
        response = litellm.completion(
            model=llm_instance.model,
            api_key=llm_instance.api_key,
            messages=[{
                "role": "user",
                "content": (
                    "If the following text is already in English, return it as-is. "
                    "If it is in Hindi, Marathi, Hinglish, or any other language, "
                    "translate it to clear simple English. "
                    "Return ONLY the English text, nothing else.\n\n"
                    f"Text: {claim}"
                )
            }],
            temperature=0.1,
            max_tokens=150
        )
        translated = response.choices[0].message.content.strip()
        return translated if translated else claim
    except Exception:
        # If translation fails, use original claim for search
        return claim


def run_crew(input_data: dict):
    """
    Runs the complete fake news verification pipeline.

    Expected input_data:
    {
        "text": "user provided claim",
        "image_provided": false
    }
    """

    # --------------------
    # Validate input
    # --------------------
    claim = input_data.get("text")
    if not claim:
        raise ValueError("No claim text provided to crew")

    # --------------------
    # Load YAML configs
    # --------------------
    agents_config = load_yaml(CONFIG_DIR / "agents.yaml")
    tasks_config = load_yaml(CONFIG_DIR / "tasks.yaml")

    # --------------------
    # Initialize LLM
    # --------------------
    llm = get_llm()

    # --------------------
    # Translate claim to English for better search results
    # --------------------
    english_claim = translate_claim_to_english(claim, llm)

    # --------------------
    # Create Agents
    # --------------------
    agents = {}
    for agent_name, cfg in agents_config.items():
        agents[agent_name] = Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=cfg["backstory"],
            allow_delegation=cfg.get("allow_delegation", False),
            verbose=cfg.get("verbose", False),
            max_iter=cfg.get("max_iter", 1),
            max_retry_limit=cfg.get("max_retry_limit", 0),
            llm=llm
        )

    # --------------------
    # Create Tasks (with context chaining)
    # --------------------
    tasks = []
    for task_name, cfg in tasks_config.items():
        task = Task(
            description=cfg["description"],
            expected_output=cfg["expected_output"],
            agent=agents[cfg["agent"]],
            context=list(tasks) if tasks else []
        )
        tasks.append(task)

    # --------------------
    # Web Search (trusted sources first, then open web)
    # --------------------
    search_results = search_with_priority(english_claim, num_results=8)

    if not search_results:
        raise ValueError("No search results returned from web search")

    # Calculate credibility score BEFORE filtering sources
    # (search_results has all fields including snippets; sources drops them)
    credibility = calculate_credibility_score(search_results, english_claim)

    # Build clean sources list for the API response
    sources = [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "source": item.get("source", ""),
            "trusted": item.get("trusted", False),
        }
        for item in search_results
        if item.get("url")  # only include items with a real URL
    ]

    # Convert search results into LLM-friendly evidence text
    evidence_text = "\n".join(
        f"- {item['title']}: {item['snippet']} ({item['source']})"
        for item in search_results
    )


    # --------------------
    # Create Crew
    # --------------------
    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=False
    )

    # --------------------
    # Run Crew (pass both original and english claim)
    # --------------------
    crew_output = crew.kickoff(
        inputs={
            "claim": claim,
            "english_claim": english_claim,
            "evidence": evidence_text
        }
    )

    # --------------------
    # Parse Result
    # --------------------
    raw = crew_output.raw if hasattr(crew_output, 'raw') else str(crew_output)
    result = parse_result(raw)

    # Override LLM-guessed confidence with calculated credibility score
    result["confidence"] = credibility["final_score"]
    result["credibility_layers"] = credibility["layers"]
    result["sources"] = sources

    return result
