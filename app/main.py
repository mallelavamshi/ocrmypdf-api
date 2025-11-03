from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
import ocrmypdf
import os
import uuid
from pathlib import Path
import pdfplumber
import pikepdf

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
    language: str = Query(default="eng", description="OCR language (eng, spa, fra, etc)"),
    deskew: bool = Query(default=True, description="Fix page skew"),
    clean: bool = Query(default=True, description="Clean/denoise image before OCR"),
    remove_background: bool = Query(default=False, description="Remove background (use cautiously)"),
    image_dpi: int = Query(default=300, description="DPI for images without DPI info (recommend 300)"),
    oversample: int = Query(default=0, description="Resample low-DPI images to this DPI (0=disabled, 300=recommended for poor scans)")
):
    """
    Process a scanned PDF and return a searchable PDF.
    Optimized for poor quality scans with preprocessing options.
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
        
        # Build OCRmyPDF arguments for better quality and performance
        ocr_params = {
            "input_file": input_path,
            "output_file": output_path,
            "language": language,
            "deskew": deskew,
            "clean": clean,  # Denoise images
            "remove_background": remove_background,
            "image_dpi": image_dpi,  # Set DPI for images without metadata
            "rotate_pages": True,  # Auto-detect rotation
            "rotate_pages_threshold": 14.0,
            "force_ocr": True,
            # Performance optimizations
            "output_type": "pdf",  # Skip PDF/A conversion for speed
            "optimize": 0,  # Disable optimization for speed
            "fast_web_view": 999999,  # Disable fast web view
        }
        
        # Add oversampling if specified (for low-quality scans)
        if oversample > 0:
            ocr_params["oversample"] = oversample
        
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
    clean: bool = Query(default=True, description="Clean/denoise before OCR"),
    image_dpi: int = Query(default=300, description="DPI for images without metadata"),
    oversample: int = Query(default=300, description="Resample low-DPI to this value (300 recommended)")
):
    """
    Extract text from a scanned PDF with preprocessing for poor quality scans.
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
        
        # Build OCR parameters optimized for quality
        ocr_params = {
            "input_file": input_path,
            "output_file": output_path,
            "language": language,
            "deskew": True,  # Always fix skew for text extraction
            "clean": clean,  # Denoise images
            "image_dpi": image_dpi,  # Handle images without DPI metadata
            "rotate_pages": True,  # Auto-detect rotation
            "rotate_pages_threshold": 14.0,
            "force_ocr": False,  # Don't re-OCR if already has text
            "skip_text": False,
            # Performance optimizations
            "output_type": "pdf",  # Skip PDF/A for speed
            "optimize": 0,  # No optimization
            "fast_web_view": 999999,
        }
        
        # Add oversampling for better OCR on poor scans
        if oversample > 0:
            ocr_params["oversample"] = oversample
        
        # Process with OCRmyPDF
        ocrmypdf.ocr(**ocr_params)
        
        # Extract text using pdfplumber
        text = ""
        page_count = 0
        
        with pdfplumber.open(output_path) as pdf:
            page_count = len(pdf.pages)
            
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                if page_text:
                    text += f"\n{'='*50}\n"
                    text += f"PAGE {page_num}\n"
                    text += f"{'='*50}\n"
                    text += page_text + "\n"
        
        return {
            "success": True,
            "text": text.strip(),
            "pages": page_count,
            "characters": len(text.strip()),
            "filename": file.filename,
            "settings_used": {
                "clean": clean,
                "image_dpi": image_dpi,
                "oversample": oversample
            }
        }
    
    except ocrmypdf.exceptions.PriorOcrFoundError:
        # PDF already has text
        try:
            text = ""
            with pdfplumber.open(input_path) as pdf:
                page_count = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages, start=1):
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n{'='*50}\n"
                        text += f"PAGE {page_num}\n"
                        text += f"{'='*50}\n"
                        text += page_text + "\n"
            
            return {
                "success": True,
                "text": text.strip(),
                "pages": page_count,
                "characters": len(text.strip()),
                "filename": file.filename,
                "note": "PDF already contained searchable text (no OCR needed)"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Text extraction failed: {str(e)}")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    
    finally:
        for temp_file in [input_path, output_path]:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass

@app.post("/ocr-high-quality")
async def ocr_high_quality(
    file: UploadFile = File(...),
    language: str = Query(default="eng", description="OCR language")
):
    """
    Aggressive OCR for very poor quality scans.
    Uses all preprocessing: clean, deskew, oversample to 300 DPI.
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
        
        # Aggressive quality settings for poor scans
        ocrmypdf.ocr(
            input_path,
            output_path,
            language=language,
            deskew=True,
            clean=True,
            image_dpi=300,
            oversample=300,  # Upsample low-res images
            rotate_pages=True,
            rotate_pages_threshold=10.0,  # More aggressive rotation
            remove_background=False,  # Usually not needed if clean is used
            force_ocr=True,
            # Performance optimizations
            output_type="pdf",
            optimize=0,
            fast_web_view=999999
        )
        
        return FileResponse(
            path=str(output_path),
            media_type="application/pdf",
            filename=f"high_quality_{file.filename}"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"High quality OCR failed: {str(e)}")
    
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
