# main.py
# Purpose: expose a web API that builds a .pptx deck and returns a download URL.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
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

from fastapi import HTTPException
from pptx import Presentation

@app.post("/create_slide")
def create_slide(req: SlideReq):
    try:
        prs = Presentation()
        # Title + Content layout is usually index 1; fall back if missing
        layout = prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[0]
        slide = prs.slides.add_slide(layout)

        # Title
        slide.shapes.title.text = req.title

        # Content placeholder -> bullets
        # Find the first body/content placeholder robustly
        body_ph = None
        for ph in slide.placeholders:
            if ph.has_text_frame and ph != slide.shapes.title:
                body_ph = ph
                break
        if body_ph is None:
            raise RuntimeError("No content placeholder with text frame found on this layout")

        tf = body_ph.text_frame
        # Clear then set first bullet as .text, others as paragraphs
        tf.clear()
        for i, b in enumerate(req.bullets):
            if i == 0:
                tf.text = b
            else:
                p = tf.add_paragraph()
                p.text = b
                p.level = 0

        # Save
        fname = f"{uuid.uuid4().hex}.pptx"
        out_path = PUBLIC_DIR / fname
        prs.save(out_path)

        base = "https://slide-agent-xs03.onrender.com"  # temporary for local
        return {"file_url": f"{base}/public/{fname}"}

    except Exception as e:
        # Surface a clear error to /docs while logging the real cause in the console
        print("ERROR /create_slide:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))