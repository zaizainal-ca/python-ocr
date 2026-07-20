from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from paddleocr import PaddleOCR
from PIL import Image, ImageFile
import io
import numpy as np
from parser import parse_mykad

ImageFile.LOAD_TRUNCATED_IMAGES = True

import os

root_path = os.getenv("ROOT_PATH", "")
app = FastAPI(title="MyKad OCR API", version="1.0", root_path=root_path)

# Enable CORS for frontend or external servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the PaddleOCR model once during server start (cached)
print("Loading PaddleOCR models...")
ocr = PaddleOCR(use_angle_cls=True, lang="en", enable_mkldnn=False)  # Uses english detection & recognition (excellent for MyKad)

@app.post("/api/ocr/mykad")
async def ocr_mykad(file: UploadFile = File(...)):
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")
        
    try:
        # Read image bytes and convert to numpy array format for PaddleOCR
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        image_np = np.array(image)
        
        # Run PaddleOCR inference
        result = ocr.ocr(image_np)
        print(f"OCR RESULT: {result}")
        
        # Parse structured MyKad fields
        parsed_data = parse_mykad(result)
        
        return {
            "success": True,
            "data": parsed_data
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")

@app.get("/health")
def health_check():
    return {"status": "healthy"}
