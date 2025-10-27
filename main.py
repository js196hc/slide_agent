# main.py
# Purpose: expose a web API that builds a .pptx deck and returns a download URL.

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, HttpUrl
from pptx import Presentation
from pathlib import Path
import uuid

app = FastAPI(
    title="Slide Generator",
    version="1.0.0",
    description="Creates simple PowerPoint decks from JSON input."
)

# Allow cross-origin requests for development.
# In production, tighten allow_origins to your domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public directory for generated files.
PUBLIC_DIR = Path("public")
PUBLIC_DIR.mkdir(exist_ok=True)

# Mount /public so files are served over HTTP.
app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")

# Request schema. Validates incoming JSON.
class SlideReq(BaseModel):
    title: str
    bullets: list[str]

class SlideResp(BaseModel):
    file_url: HttpUrl

@app.post("/create_slide", response_model=SlideResp)
def create_slide(req: SlideReq, request: Request):
    try:
        prs = Presentation()
        layout = prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[0]
        slide = prs.slides.add_slide(layout)

        # Title
        slide.shapes.title.text = req.title

        # Body bullets (robust)
        body_ph = None
        for ph in slide.placeholders:
            if ph.has_text_frame and ph != slide.shapes.title:
                body_ph = ph
                break
        if body_ph is None:
            raise HTTPException(status_code=500, detail="No content placeholder found on layout")

        tf = body_ph.text_frame
        # clear any default text
        try:
            tf.clear()
        except AttributeError:
            tf.text = ""

        for i, b in enumerate(req.bullets):
            if i == 0:
                tf.text = b
            else:
                p = tf.add_paragraph()
                p.text = b
                p.level = 0

        fname = f"{uuid.uuid4().hex}.pptx"
        out_path = PUBLIC_DIR / fname
        prs.save(out_path)

        base = str(request.base_url).rstrip("/")  # works locally and on Render
        return SlideResp(file_url=f"{base}/public/{fname}")

    except Exception as e:
        print("ERROR /create_slide:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title="Slide Generator",
        version="1.0.0",
        description="Creates simple PowerPoint decks from JSON input.",
        routes=app.routes,
    )
    schema["servers"] = [
        {"url": "https://slide-agent-xs03.onrender.com", "description": "Render deployment"}
    ]
    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get("/health")
def health(): return {"ok": True}