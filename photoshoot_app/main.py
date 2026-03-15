import base64
import os
import uuid
from datetime import datetime, timezone

import requests
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

APP_ROOT = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(APP_ROOT, "outputs")

os.makedirs(OUTPUT_DIR, exist_ok=True)

app = FastAPI()
app.mount("/static", StaticFiles(directory=os.path.join(APP_ROOT, "static")), name="static")
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")

templates = Jinja2Templates(directory=os.path.join(APP_ROOT, "templates"))

XAI_BASE_URL = "https://api.x.ai"
XAI_MODEL = "grok-imagine-image"

STYLE_PRESETS = {
    "classic_bw": {
        "title": "Classic B&W Studio",
        "prompt": "Black-and-white studio portrait, soft directional key light, subtle fill, medium contrast, clean backdrop, editorial fashion mood, sharp focus, natural skin texture, professional headshot composition.",
    },
    "modern_color": {
        "title": "Modern Color Editorial",
        "prompt": "Modern color editorial portrait, softbox lighting, shallow depth of field, clean backdrop, warm tones, professional fashion photography, crisp details, natural skin texture.",
    },
    "corporate": {
        "title": "Corporate Headshot",
        "prompt": "Corporate studio headshot, neutral background, soft even lighting, realistic skin tone, professional business portrait, clean and polished, natural expression.",
    },
}


def build_prompt(style_key: str, extra_notes: str) -> str:
    style = STYLE_PRESETS.get(style_key, STYLE_PRESETS["classic_bw"])
    base = style["prompt"]
    extra = (extra_notes or "").strip()
    if extra:
        return f"{base} Additional notes: {extra}"
    return base


def call_xai_image_edit(image_bytes: bytes, prompt: str, size: str) -> bytes:
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing XAI_API_KEY")

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_uri = f"data:image/png;base64,{image_b64}"

    url = f"{XAI_BASE_URL}/v1/images/edits"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": XAI_MODEL,
        "prompt": prompt,
        "image": data_uri,
        "size": size,
        "response_format": "b64_json",
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(f"xAI API error {response.status_code}: {response.text}")

    payload = response.json()
    if not payload.get("data"):
        raise RuntimeError("xAI API returned no image data")

    b64_image = payload["data"][0].get("b64_json")
    if not b64_image:
        raise RuntimeError("xAI API returned empty image")

    return base64.b64decode(b64_image)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "styles": STYLE_PRESETS,
        },
    )


@app.post("/generate", response_class=HTMLResponse)
def generate(
    request: Request,
    selfie: UploadFile = File(...),
    style: str = Form("classic_bw"),
    size: str = Form("1024x1024"),
    extra_notes: str = Form(""),
    consent: str = Form(None),
):
    if consent != "on":
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "styles": STYLE_PRESETS,
                "error": "Please confirm you have consent to upload this image.",
            },
        )

    image_bytes = selfie.file.read()
    if not image_bytes:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "styles": STYLE_PRESETS,
                "error": "Uploaded file is empty.",
            },
        )

    prompt = build_prompt(style, extra_notes)

    try:
        output_bytes = call_xai_image_edit(image_bytes, prompt, size)
    except Exception as exc:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "styles": STYLE_PRESETS,
                "error": str(exc),
            },
        )

    filename = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex}.png"
    output_path = os.path.join(OUTPUT_DIR, filename)
    with open(output_path, "wb") as handle:
        handle.write(output_bytes)

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "image_url": f"/outputs/{filename}",
        },
    )
