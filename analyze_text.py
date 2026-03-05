"""
analyze_text.py

Purpose:
- Load the legal FAISS vector store
- Retrieve relevant legal context
- Send ad text + retrieved context to OpenAI model
- Return structured JSON compliance analysis (English only)
"""

# analyze_text.py

import os
import re
import json
import traceback
from pathlib import Path
from typing import Dict, Any, List

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS


# =========================
# Config
# =========================

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

TEMPERATURE = 0

BASE_DIR = Path(__file__).resolve().parent
VECTOR_DIR = BASE_DIR / "vectordb" / "laws_faiss"

TOP_K = 6
MAX_ISSUES = 6


# =========================
# Scoring Rules
# =========================

CATEGORY_MAX = 25

DEDUCTION_RULES = {
    "Claims Accuracy & Substantiation": {
        "LOW": 3,
        "MEDIUM": 7,
        "HIGH": 12,
    },
    "Marketing Ethics & Transparency": {
        "LOW": 3,
        "MEDIUM": 6,
        "HIGH": 10,
    },
    "Tone, Inclusivity & Representation": {
        "LOW": 2,
        "MEDIUM": 5,
        "HIGH": 8,
    },
    "Privacy, Data Practices & User Consent": {
        "LOW": 4,
        "MEDIUM": 8,
        "HIGH": 12,
    },
}

RISK_LEVELS = [
    (80, "Low Risk"),
    (55, "Medium Risk"),
    (0, "High Risk"),
]


# =========================
# Utilities
# =========================

def _require_api_key():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set")


def _load_vectorstore():
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    return FAISS.load_local(
        str(VECTOR_DIR),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def _format_context(docs) -> str:

    blocks = []

    for d in docs:

        law = d.metadata.get("law", "Unknown")

        text = re.sub(r"\s+", " ", d.page_content.strip())[:800]

        blocks.append(f"{law}: {text}")

    return "\n".join(blocks)


def _extract_json(text: str) -> Dict[str, Any]:

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON found in LLM output")

    return json.loads(text[start:end + 1])


def _make_llm():

    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=TEMPERATURE,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


# =========================
# Prompt
# =========================

def _build_prompt(ad_text: str, law_context: str) -> str:

    return f"""
You are a senior Canadian advertising compliance expert.

TASK

Identify all compliance issues in the advertisement.

Each issue must belong to exactly one category.

Quote the exact problematic phrase from the ad as evidence.

Then propose safer rewrite alternatives.

Use the provided Canadian law excerpts as guidance.


CATEGORIES

Claims Accuracy & Substantiation  
Marketing Ethics & Transparency  
Tone, Inclusivity & Representation  
Privacy, Data Practices & User Consent  


LAW CONTEXT

{law_context}


AD TEXT

{ad_text}


OUTPUT JSON ONLY

{{
  "flagged_issues": [
    {{
      "issue_id": "ISSUE_001",
      "category": "Claims Accuracy & Substantiation",
      "severity": "HIGH | MEDIUM | LOW",
      "law": "Competition Act",
      "section": "string",
      "explanation": "Explain why this violates advertising compliance",
      "law_basis": "Explain which principle of the law applies",
      "evidence": "exact quote from the ad"
    }}
  ],

  "rewrite": {{
    "title": "safer rewritten title",
    "bullets": [
      "rewrite bullet 1",
      "rewrite bullet 2"
    ]
  }},

  "rewrite_explanation": "Explain why the rewritten version is safer and compliant.",

  "notes": [
    "optional note"
  ]
}}
"""


# =========================
# Scoring Engine
# =========================

def _normalize_severity(sev: str) -> str:

    if not sev:
        return "LOW"

    sev = sev.upper()

    if "HIGH" in sev:
        return "HIGH"

    if "MEDIUM" in sev:
        return "MEDIUM"

    return "LOW"


def _score_categories(issues: List[Dict[str, Any]]) -> Dict[str, int]:

    scores = {cat: CATEGORY_MAX for cat in DEDUCTION_RULES}

    for issue in issues:

        cat = issue["category"]

        sev = _normalize_severity(issue["severity"])

        issue["severity"] = sev

        if cat in DEDUCTION_RULES:
            scores[cat] -= DEDUCTION_RULES[cat].get(sev, 0)

    for cat in scores:
        scores[cat] = max(0, min(CATEGORY_MAX, scores[cat]))

    return scores


def _risk_from_score(total: int) -> str:

    for cutoff, label in RISK_LEVELS:

        if total >= cutoff:
            return label

    return "High Risk"


# =========================
# Public API
# =========================

_vectorstore = None


def analyze_ad_text(ad_text: str) -> Dict[str, Any]:

    try:

        _require_api_key()

        global _vectorstore

        if _vectorstore is None:
            _vectorstore = _load_vectorstore()

        retriever = _vectorstore.as_retriever(search_kwargs={"k": TOP_K})

        docs = retriever.invoke(ad_text)

        context = _format_context(docs)

        llm = _make_llm()

        prompt = _build_prompt(ad_text, context)

        raw = llm.invoke(prompt)

        parsed = _extract_json(raw.content)

        issues = parsed.get("flagged_issues", [])

        # 限制最大 issue 数量

        issues = issues[:MAX_ISSUES]

        # 计算评分

        category_scores = _score_categories(issues)

        overall_score = sum(category_scores.values())

        risk_level = _risk_from_score(overall_score)

        rewrite = parsed.get("rewrite", {})

        bullets = rewrite.get("bullets", [])

        title = rewrite.get("title", "")

        rewrite_text = title + "\n" + "\n".join(bullets)

        return {

            "overall_score": overall_score,

            "risk_level": risk_level,

            "category_breakdown": [
                {"category": k, "score": v}
                for k, v in category_scores.items()
            ],

            "flagged_issues": issues,

            "rewrite_suggestions": {

                "suggested_rewrite": rewrite_text,

                "safer_alternatives": bullets,

                "rewrite_explanation": parsed.get("rewrite_explanation", ""),

            },

            "notes": parsed.get("notes", []),
        }

    except Exception:

        raise RuntimeError(
            "analyze_ad_text failed:\n" + traceback.format_exc()
        )
