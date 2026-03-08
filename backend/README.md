# Fake News Verification Backend

This backend powers an AI-based fake news verification system that
analyzes user-provided claims and evaluates them using web evidence and
an LLM-powered multi-agent pipeline.

The system uses **CrewAI agents**, **web search evidence**, and **Gemini
LLM** to determine whether a claim is likely true, false, or misleading.

------------------------------------------------------------------------

## 🚀 Features

-   Multi-agent AI verification system
-   Real-time web search evidence collection
-   AI reasoning using Gemini LLM
-   Multilingual explanations (English, Hindi, Marathi)
-   FastAPI backend API
-   Modular configuration using YAML
-   Clean architecture separating API, agents, tasks, and tools

------------------------------------------------------------------------

## 🧠 Architecture Overview

User Input (Text / Image)
          ↓
FastAPI Endpoint (/verify)
          ↓
CrewAI Pipeline
          ↓
Web Search Evidence
          ↓
Claim Analysis
          ↓
Verification Decision
          ↓
Multilingual Explanation (EN / HI / MR)

------------------------------------------------------------------------

## 📂 Project Structure

```
📂backend
|
├── 📁 config
│   ├── ⚙️ agents.yaml
│   └── ⚙️ tasks.yaml
├── 📁 crew
│   ├── 🐍 __init__.py
│   ├── 🐍 crew.py
│   └── 🐍 llm.py
├── 📁 server
│   ├── 🐍 __init__.py
│   └── 🐍 api.py
├── 📁 tools
│   ├── 🐍 __init__.py
│   └── 🐍 web_search.py
├── ⚙️ .envExample
├── ⚙️ .gitignore
├── 📝 README.md
├── 🐍 main.py
├── ⚙️ pyproject.toml
└── 📄 uv.lock
```

------------------------------------------------------------------------

## ⚙️ Technology Stack

  Component            Technology
  -------------------- ---------------
  API Framework        FastAPI
  AI Agents            CrewAI
  LLM                  Google Gemini
  Web Search           SerpAPI
  Dependency Manager   uv
  Environment Config   python-dotenv

------------------------------------------------------------------------

## 🧑‍💻 Installation

### 1. Clone the repository

``` bash
git clone <repository-url>
cd backend
```

### 2. Install dependencies using uv

``` bash
uv add fastapi uvicorn python-multipart crewai "crewai[litellm]" google-generativeai requests python-dotenv
```

### 3. Create `.env` file

    LLM_API_KEY=your_gemini_api_key
    SEARCH_API_KEY=your_serpapi_key
    SEARCH_PROVIDER=serpapi

### 4. Start the server

``` bash
uv run uvicorn main:app --reload
```

Server runs at:

    http://127.0.0.1:8000

------------------------------------------------------------------------

## 🧪 Testing the API

Open Swagger UI:

    http://127.0.0.1:8000/docs

Use **POST /verify** endpoint.

Example request:

    text: Government has banned ₹500 notes from tomorrow

Example response:

``` json
{
  "status": "success",
  "languages": ["en", "hi", "mr"],
  "data": {
    "verdict": "Likely False",
    "confidence": 82,
    "english": "...",
    "hindi": "...",
    "marathi": "..."
  }
}
```

------------------------------------------------------------------------

## 🤖 AI Agents

The system uses multiple specialized agents:

**Input Agent**\
Interprets the user claim, including mixed-language or romanized text.

**Search Agent**\
Analyzes search results and extracts relevant evidence.

**Analysis Agent**\
Compares the claim with collected evidence.

**Verification Agent**\
Determines whether the claim is true, false, or misleading.

**Final Response Agent**\
Generates multilingual explanations for users.

------------------------------------------------------------------------

## 🔍 Web Evidence Collection

The system performs real-time web searches using SerpAPI to gather:

-   Article titles
-   Snippets
-   Source references

This ensures the verification process is **evidence-based**.

------------------------------------------------------------------------

## 🌍 Multilingual Output

The final explanation is generated in:

-   English
-   Hindi
-   Marathi

This improves accessibility for diverse users.

------------------------------------------------------------------------

## 🔐 Environment Variables

  Variable          Purpose
  ----------------- -------------------------------
  LLM_API_KEY       Gemini API key
  SEARCH_API_KEY    SerpAPI key
  SEARCH_PROVIDER   Search provider configuration

------------------------------------------------------------------------

## ⚠️ Disclaimer

This system assists users in evaluating the credibility of claims but
does not guarantee absolute truth. Results depend on available public
information and AI interpretation.

------------------------------------------------------------------------

## 📌 Future Improvements

-   Trusted source credibility scoring
-   Reverse image search verification
-   Claim history caching
-   Browser extension integration
-   Real-time fact-check database integration

------------------------------------------------------------------------

## 📄 License

This project is for educational and research purposes.
