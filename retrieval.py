import re
from pathlib import Path

POLICY_PATH = Path(__file__).with_name("student_policy.txt")

def _tokens(text):
    stop_words = {"what", "is", "the", "a", "an", "on", "in", "of", "to", "can", "i", "my", "does", "about", "for", "me", "please"}
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in stop_words}

def retrieve_policy(question, threshold=0.12):
    """Small transparent retrieval: rank handbook paragraphs by token overlap."""
    paragraphs = [p.strip() for p in POLICY_PATH.read_text(encoding="utf-8").split("\n\n") if p.strip()]
    q = _tokens(question)
    ranked = []
    for i, para in enumerate(paragraphs):
        words = _tokens(para)
        score = len(q & words) / max(len(q), 1)
        ranked.append((score, i, para))
    ranked.sort(reverse=True)
    selected = [(s, i, p) for s, i, p in ranked[:2] if s >= threshold]
    if not selected:
        return "", []
    return "\n\n".join(p for _, _, p in selected), [f"policy_chunk_{i+1}" for _, i, _ in selected]
