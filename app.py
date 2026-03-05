# app.py
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from analyze_text import analyze_ad_text
import os
print("OPENAI_API_KEY exists:", bool(os.getenv("OPENAI_API_KEY")))

# Import the REAL function name from analyze_multimodal.py
# Your file defines: analyze_ad_text_and_image(ad_text, image_bytes, mime_type) -> Dict
try:
    from analyze_multimodal import analyze_ad_text_and_image as analyze_multimodal
except Exception:
    analyze_multimodal = None


app = FastAPI(title="Compliance Bot API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    ad_text: str


def _no_cache(payload: Dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        payload,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


def _fix_scores(result_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforce score consistency:
    - overall_score = sum of 4 category scores
    - risk_level derived from overall_score
    """
    if not isinstance(result_obj, dict):
        return result_obj

    # Some code returns {"result": {...}}; normalize
    core = result_obj.get("result") if "result" in result_obj and isinstance(result_obj.get("result"), dict) else result_obj

    cb = core.get("category_breakdown", [])
    if isinstance(cb, list) and len(cb) > 0:
        total = 0
        for item in cb:
            if isinstance(item, dict) and isinstance(item.get("score"), (int, float)):
                total += int(item["score"])
        core["overall_score"] = int(total)

        # risk mapping: 80–100 Low, 55–79 Medium, 0–54 High
        if total >= 80:
            core["risk_level"] = "Low Risk"
        elif total >= 55:
            core["risk_level"] = "Medium Risk"
        else:
            core["risk_level"] = "High Risk"

    # Put back if it was nested
    if "result" in result_obj and isinstance(result_obj.get("result"), dict):
        result_obj["result"] = core
        return result_obj
    return core


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    try:
        if not request.ad_text or not request.ad_text.strip():
            raise HTTPException(status_code=400, detail="ad_text cannot be empty")

        result_json = analyze_ad_text(request.ad_text)
        result_json = _fix_scores(result_json)

        return _no_cache({"result": result_json})

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"analyze failed: {e}")


@app.post("/analyze_multimodal")
async def analyze_multimodal_endpoint(
    ad_text: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
):
    if analyze_multimodal is None:
        raise HTTPException(status_code=501, detail="Multimodal analysis is not enabled in this build.")

    if image is None:
        raise HTTPException(status_code=400, detail="image is required for multimodal analysis")

    try:
        img_bytes = await image.read()
        mime_type = image.content_type or "image/jpeg"
        text = (ad_text or "").strip()

        # Call your real multimodal function
        mm = analyze_multimodal(ad_text=text, image_bytes=img_bytes, mime_type=mime_type)

        # mm is: {"result": <text engine result>, "image_summary": {...}}
        # Fix scores inside mm["result"]
        if isinstance(mm, dict) and isinstance(mm.get("result"), dict):
            mm["result"] = _fix_scores(mm["result"])

        return _no_cache(mm)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"analyze_multimodal failed: {e}")
