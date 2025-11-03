from fastapi import FastAPI, File, UploadFile, HTTPException
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
    language: str = "eng",
    deskew: bool = True,
    remove_background: bool = False
):
    """
    Process a scanned PDF and return a searchable PDF
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    file_id = str(uuid.uuid4())
    input_path = TEMP_DIR / f"{file_id}_input.pdf"
    output_path = TEMP_DIR / f"{file_id}_output.pdf"
    
    try:
        # Save uploaded file
        with open(input_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Process with OCRmyPDF
        ocrmypdf.ocr(
            input_path,
            output_path,
            language=language,
            deskew=deskew,
            remove_background=remove_background,
            force_ocr=True
        )
        
        # Return the processed file
        return FileResponse(
            path=str(output_path),
            media_type="application/pdf",
            filename=f"searchable_{file.filename}"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")
    
    finally:
        # Cleanup input file
        if input_path.exists():
            try:
                input_path.unlink()
            except:
                pass

@app.post("/extract-text")
async def extract_text(
    file: UploadFile = File(...), 
    language: str = "eng"
):
    """
    Extract text from a scanned PDF using pdfplumber
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    file_id = str(uuid.uuid4())
    input_path = TEMP_DIR / f"{file_id}_input.pdf"
    output_path = TEMP_DIR / f"{file_id}_output.pdf"
    
    try:
        # Save uploaded file
        with open(input_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # First, OCR the PDF to ensure it has text
        ocrmypdf.ocr(
            input_path, 
            output_path, 
            language=language,
            force_ocr=False,  # Don't re-OCR if already has text
            skip_text=False
        )
        
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
            "filename": file.filename
        }
    
    except ocrmypdf.exceptions.PriorOcrFoundError:
        # PDF already has text, extract directly
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
                "note": "PDF already contained searchable text"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Text extraction failed: {str(e)}")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    
    finally:
        # Cleanup temporary files
        for temp_file in [input_path, output_path]:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass

@app.get("/info")
async def get_pdf_info(pdf_url: str = None):
    """
    Get PDF metadata and page count
    """
    if not pdf_url:
        raise HTTPException(status_code=400, detail="pdf_url parameter is required")
    
    return {"message": "Feature coming soon", "status": "not_implemented"}

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
            if current_time - file_path.stat().st_mtime > 3600:  # 1 hour
                file_path.unlink()
                count += 1
        return {"message": f"Cleaned up {count} temporary files", "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")
