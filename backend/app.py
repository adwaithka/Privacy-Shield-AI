"""
app.py v3.3 — adds QR code masking support
"""

import sys

# Windows consoles default to cp1252; allow Unicode log output safely
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import os
import json
import base64
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from presidio_anonymizer import AnonymizerEngine

from extractor import extract_text
from detector import analyze_text, AVAILABLE_TARGETS, get_detector_info
from redactor import produce_redacted_file

app = FastAPI(title="Privacy Shield AI", version="3.3")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".txt",
    ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp",
}
IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp",
}

_anonymizer = AnonymizerEngine()


@app.get("/")
def home():
    info = get_detector_info()
    return {
        "message": "Privacy Shield AI Running",
        "version": "3.4",
        "spacy_model": info["spacy_model"],
        "detection_layers": ["presidio", "native_spacy", "custom_patterns", "rule_heuristics"],
    }


@app.get("/targets")
def get_targets():
    return {"targets": AVAILABLE_TARGETS}


@app.post("/analyze")
async def analyze_file(
    file: UploadFile = File(...),
    mask_targets: str = Form(default="all"),
    mask_face: str = Form(default="true"),
    mask_qr: str = Form(default="true"),
):
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    try:
        targets = json.loads(mask_targets) if mask_targets.strip().startswith("[") else [mask_targets.strip()]
    except Exception:
        targets = ["all"]

    should_mask_face = mask_face.lower() not in ("false", "0", "no")
    # QR masking: on when "all" mode OR "qr_code" explicitly selected
    should_mask_qr = (
        mask_qr.lower() not in ("false", "0", "no")
        and ("all" in targets or "qr_code" in targets)
    )

    raw_bytes = await file.read()
    tmp_fd, filepath = tempfile.mkstemp(suffix=ext, dir=str(UPLOAD_DIR))
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(raw_bytes)

        print(f"\n{'='*60}")
        print(f"FILE    : {filename}")
        print(f"TARGETS : {targets}")
        print(f"FACE    : {should_mask_face}  QR: {should_mask_qr}")
        print(f"{'='*60}")

        extracted_text = extract_text(filepath)
        print(f"\n--- EXTRACTED TEXT (first 400 chars) ---")
        print(extracted_text[:400])
        print("---")

        if not extracted_text.strip():
            raise HTTPException(status_code=422, detail="No text could be extracted.")

        results = analyze_text(extracted_text, targets)

        entities = [
            {"type": r.entity_type, "text": extracted_text[r.start:r.end], "score": round(r.score, 2)}
            for r in results
        ]

        print(f"\n--- ENTITIES FOUND ({len(entities)}) ---")
        for e in entities:
            print(f"  {e['type']:20} : {repr(e['text'])}")
        print("---")

        masked_text = _anonymizer.anonymize(
            text=extracted_text, analyzer_results=results
        ).text if results else extracted_text

        is_image = ext in IMAGE_EXTENSIONS
        redacted_bytes = produce_redacted_file(
            file_path=filepath,
            extracted_text=extracted_text,
            masked_text=masked_text,
            entities=entities,
            results=results,
            is_image=is_image,
            original_filename=filename,
            mask_face=should_mask_face,
            mask_qr=should_mask_qr,
        )

        encoded = base64.b64encode(redacted_bytes).decode("utf-8")

    except HTTPException:
        raise
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            os.unlink(filepath)
        except OSError:
            pass

    response = {
        "filename": filename,
        "file_type": "image" if is_image else "document",
        "mask_targets": targets,
        "entities_found": len(entities),
        "entities": entities,
        "masked_text": masked_text,
        "redacted_file_b64": encoded,
    }
    response["redacted_image_b64" if is_image else "redacted_pdf_b64"] = encoded
    return response
