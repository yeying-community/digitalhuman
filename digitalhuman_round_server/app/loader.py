import re
from typing import Any, Dict, List, Optional, Tuple

QUESTION_PREFIX_RE = re.compile(r"^\s*【([^】]+)】\s*")

def extract_questions(payload: Dict[str, Any]) -> Tuple[List[str], List[Optional[str]]]:
    """
    Preferred: payload["questions"] -> List[str]
    Fallback: payload["categorized_questions"] -> List[str] (flatten)
    If neither, try common text fields as one single question.
    Returns: (questions, categories)
    """
    questions: List[str] = []
    categories: List[Optional[str]] = []

    def push(q: str):
        q = (q or "").strip()
        if not q:
            return
        cat = None
        m = QUESTION_PREFIX_RE.match(q)
        if m:
            cat = m.group(1).strip()
        questions.append(q)
        categories.append(cat)

    raw = payload.get("questions")
    if isinstance(raw, list) and raw:
        for item in raw:
            if isinstance(item, str):
                push(item)
            elif isinstance(item, dict):
                # tolerate dict form like {"question": "...", "category": "..."}
                text = item.get("question") or item.get("text") or item.get("content") or ""
                cat  = item.get("category")
                qtxt = (text or "").strip()
                if qtxt:
                    questions.append(qtxt)
                    categories.append(cat)
    elif isinstance(payload.get("categorized_questions"), dict):
        for _, arr in payload["categorized_questions"].items():
            if isinstance(arr, list):
                for q in arr:
                    if isinstance(q, str):
                        push(q)
                    elif isinstance(q, dict):
                        text = q.get("question") or q.get("text") or q.get("content") or ""
                        push(text)
    else:
        # last resort: try some fields as a single question
        for key in ("content", "text", "output", "question"):
            v = payload.get(key)
            if isinstance(v, str) and v.strip():
                push(v.strip())
                break

    return questions, categories
