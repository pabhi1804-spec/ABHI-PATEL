"""Groq LLM connection (OpenAI-compatible chat API). Standard library only - nothing extra to install.

The API key is read from the GROQ_API_KEY environment variable, or from a local .env file.
If no real key is set, `is_configured()` is False and the agent uses its rule-based route instead.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class LLMError(Exception):
    pass


def _load_env_file():
    path = Path(__file__).with_name(".env")
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env_file()


def get_key():
    key = os.environ.get("GROQ_API_KEY", "").strip()
    return "" if (not key or "PASTE" in key.upper()) else key


def get_model():
    return os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def is_configured():
    return bool(get_key())


def _post(payload):
    req = urllib.request.Request(
        GROQ_URL, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {get_key()}", "Content-Type": "application/json",
                 "User-Agent": "student-support-agent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise LLMError(f"Groq HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}")
    except Exception as e:  # network down, timeout, bad JSON ...
        raise LLMError(str(e))


def chat(messages, tools):
    """One model call. Returns (assistant_message_dict, prompt_tokens, completion_tokens)."""
    data = _post({"model": get_model(), "messages": messages, "tools": tools,
                  "tool_choice": "auto", "temperature": 0, "max_tokens": 600})
    try:
        usage = data.get("usage", {})
        return data["choices"][0]["message"], usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    except (KeyError, IndexError):
        raise LLMError("Unexpected response from Groq")
