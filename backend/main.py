import os
import logging

# ── Silence noisy third-party loggers ─────────────────────────────────────
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)
logging.getLogger("crewai.telemetry").setLevel(logging.WARNING)
logging.getLogger("opentelemetry").setLevel(logging.WARNING)

# Disable CrewAI telemetry entirely (prevents 30-sec Timeout on startup)
os.environ.setdefault("CREWAI_TELEMETRY_OPT_OUT", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
# ──────────────────────────────────────────────────────────────────────────

from server.api import app
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
