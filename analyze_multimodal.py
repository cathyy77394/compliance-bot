import base64
import json
import re
from typing import Dict

from langchain_openai import ChatOpenAI

from analyze_text import analyze_ad_text



VISION_MODEL_NAME = "gpt-4.1-mini"

vision_llm = ChatOpenAI(
    model=VISION_MODEL_NAME,
    temperature=0,
)


# =========================
# Utilities
# =========================

def _image_bytes_to_data_url(image_bytes: bytes, mime_type: str) -> str:

    b64 = base64.b64encode(image_bytes).decode("utf-8")

    return f"data:{mime_type};base64,{b64}"


def _safe_json_extract(text: str):

    """
    Extract JSON from model output safely.
    Handles cases like ```json ... ```
    """

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("Vision model returned no JSON")

    return json.loads(text[start:end + 1])


# =========================
# Vision Extraction
# =========================

def extract_ad_info_from_image(image_bytes: bytes, mime_type: str) -> Dict:

    data_url = _image_bytes_to_data_url(image_bytes, mime_type)

    prompt = """
You are an assistant that extracts advertising-relevant information from an ad image.

Return ONLY valid JSON.

JSON format:

{
  "extracted_text": "all readable text from the image",
  "key_claims": ["claim1", "claim2"],
  "offers_and_pricing": ["offer statement"],
  "disclosures_present": ["terms or disclaimers found"],
  "notable_visual_elements": ["before/after imagery", "celebrity endorsement", "medical imagery"],
  "potential_risk_signals": ["absolute claims", "missing conditions", "unclear pricing basis"]
}
""".strip()

    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]

    try:

        resp = vision_llm.invoke(
            [{"role": "user", "content": content}]
        )

        parsed = _safe_json_extract(resp.content)

        return parsed

    except Exception as e:

        raise RuntimeError(
            "Vision extraction failed.\n"
            f"Original error: {e}"
        )


# =========================
# Multimodal Analysis
# =========================

def analyze_ad_text_and_image(
    ad_text: str,
    image_bytes: bytes,
    mime_type: str
) -> Dict:

    try:

        image_info = extract_ad_info_from_image(image_bytes, mime_type)

    except Exception:

        # fallback: analyze only text if vision fails
        image_info = {
            "extracted_text": "",
            "key_claims": [],
            "offers_and_pricing": [],
            "disclosures_present": [],
            "notable_visual_elements": [],
            "potential_risk_signals": []
        }

    # Limit text size (prevents extremely long prompts)

    extracted_text = image_info.get("extracted_text", "")[:1500]

    combined_ad = (
        "[USER PROVIDED TEXT]\n"
        f"{ad_text}\n\n"

        "[IMAGE EXTRACTED TEXT]\n"
        f"{extracted_text}\n\n"

        "[IMAGE KEY CLAIMS]\n- "
        + "\n- ".join(image_info.get("key_claims", []))

        + "\n\n[IMAGE OFFERS & PRICING]\n- "
        + "\n- ".join(image_info.get("offers_and_pricing", []))

        + "\n\n[IMAGE DISCLOSURES PRESENT]\n- "
        + "\n- ".join(image_info.get("disclosures_present", []))

        + "\n\n[IMAGE NOTABLE VISUAL ELEMENTS]\n- "
        + "\n- ".join(image_info.get("notable_visual_elements", []))

        + "\n\n[IMAGE POTENTIAL RISK SIGNALS]\n- "
        + "\n- ".join(image_info.get("potential_risk_signals", []))
    )

    # reuse existing RAG + scoring engine

    result = analyze_ad_text(combined_ad)

    return {
        "result": result,
        "image_summary": image_info
    }
