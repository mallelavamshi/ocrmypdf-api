from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
import ocrmypdf
import os
import uuid
from pathlib import Path
import subprocess
import tempfile
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

app = FastAPI(title="OCRmyPDF API", version="1.0.0")

TEMP_DIR = Path("/tmp/ocr_files")
TEMP_DIR.mkdir(exist_ok=True)

@app.get("/")
async def root():
    return {"message": "OCRmyPDF API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/ocr")
async def process_pdf(
    file: UploadFile = File(...),
    language: str = Query(default="eng", description="OCR language"),
    redo_ocr: bool = Query(default=False, description="Re-OCR pages with existing text")
):
    """
    Process a scanned PDF and return a searchable PDF using simple OCR
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    file_id = str(uuid.uuid4())
    input_path = TEMP_DIR / f"{file_id}_input.pdf"
    output_path = TEMP_DIR / f"{file_id}_output.pdf"
    
    try:
        with open(input_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Build OCR parameters
        ocr_params = {
            "input_file": input_path,
            "output_file": output_path,
            "language": language,
            "output_type": "pdf",  # Skip PDF/A
            "optimize": 0,
            "skip_big": 15,
            "tesseract_timeout": 180
        }
        
        # Add redo-ocr if requested
        if redo_ocr:
            ocr_params["redo_ocr"] = True
        
        # Process with OCRmyPDF
        ocrmypdf.ocr(**ocr_params)
        
        return FileResponse(
            path=str(output_path),
            media_type="application/pdf",
            filename=f"searchable_{file.filename}"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")
    
    finally:
        if input_path.exists():
            try:
                input_path.unlink()
            except:
                pass


@app.post("/extract-text")
async def extract_text(
    file: UploadFile = File(...), 
    language: str = Query(default="eng", description="OCR language"),
    psm: int = Query(default=3, description="Tesseract PSM mode (3=auto, 6=single block, 11=sparse text)")
):
    """
    Extract text using Tesseract directly with PSM control.
    PSM modes:
    - 3: Fully automatic (default)
    - 6: Assume a single uniform block of text
    - 11: Sparse text. Find as much text as possible
    - 12: Sparse text with OSD (orientation detection)
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    file_id = str(uuid.uuid4())
    input_path = TEMP_DIR / f"{file_id}_input.pdf"
    
    try:
        with open(input_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Convert PDF to images
        images = convert_from_path(input_path, dpi=300)
        
        # Extract text from each page using Tesseract with specified PSM
        all_text = ""
        page_count = len(images)
        
        for page_num, image in enumerate(images, start=1):
            # Configure Tesseract with PSM mode
            custom_config = f'--psm {psm} --oem 3'
            
            # Extract text
            page_text = pytesseract.image_to_string(
                image,
                lang=language,
                config=custom_config
            )
            
            if page_text.strip():
                all_text += f"\n{'='*50}\n"
                all_text += f"PAGE {page_num}\n"
                all_text += f"{'='*50}\n"
                all_text += page_text + "\n"
        
        return {
            "success": True,
            "text": all_text.strip(),
            "pages": page_count,
            "characters": len(all_text.strip()),
            "filename": file.filename,
            "settings_used": {
                "language": language,
                "psm_mode": psm,
                "dpi": 300
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {str(e)}")
    
    finally:
        if input_path.exists():
            try:
                input_path.unlink()
            except:
                pass

@app.post("/extract-text-simple")
async def extract_text_simple(
    file: UploadFile = File(...), 
    language: str = Query(default="eng", description="OCR language")
):
    """
    Simple text extraction with minimal processing - best for clean scans
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    file_id = str(uuid.uuid4())
    input_path = TEMP_DIR / f"{file_id}_input.pdf"
    
    try:
        with open(input_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Convert PDF to images at 300 DPI
        images = convert_from_path(input_path, dpi=300)
        
        all_text = ""
        
        for page_num, image in enumerate(images, start=1):
            # Use PSM 6 (single uniform block) - usually best for documents
            page_text = pytesseract.image_to_string(
                image,
                lang=language,
                config='--psm 6 --oem 3'
            )
            
            if page_text.strip():
                all_text += f"\n{'='*50}\n"
                all_text += f"PAGE {page_num}\n"
                all_text += f"{'='*50}\n"
                all_text += page_text + "\n"
        
        return {
            "success": True,
            "text": all_text.strip(),
            "pages": len(images),
            "characters": len(all_text.strip()),
            "filename": file.filename
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
    
    finally:
        if input_path.exists():
            try:
                input_path.unlink()
            except:
                pass

@app.delete("/cleanup")
async def cleanup_temp_files():
    """
    Cleanup temporary files older than 1 hour
    """
    import time
    try:
        count = 0
        current_time = time.time()
        for file_path in TEMP_DIR.glob("*.pdf"):
            if current_time - file_path.stat().st_mtime > 3600:
                file_path.unlink()
                count += 1
        return {"message": f"Cleaned up {count} temporary files", "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")
