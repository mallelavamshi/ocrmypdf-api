from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
import ocrmypdf
import os
import tempfile
import uuid
from pathlib import Path
import PyPDF2

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
    
    # Generate unique filenames
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
            path=output_path,
            media_type="application/pdf",
            filename=f"searchable_{file.filename}",
            background=None
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")
    
    finally:
        # Cleanup input file immediately
        if input_path.exists():
            input_path.unlink()

@app.post("/extract-text")
async def extract_text(file: UploadFile = File(...), language: str = "eng"):
    """
    Extract text from a scanned PDF
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
        
        # Process with OCRmyPDF to add text layer
        ocrmypdf.ocr(
            input_path, 
            output_path, 
            language=language,
            force_ocr=True,
            skip_text=False
        )
        
        # Extract text using PyPDF2
        text = ""
        page_count = 0
        
        with open(output_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            page_count = len(pdf_reader.pages)
            
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- Page {page_num + 1} ---\n"
                        text += page_text
                except Exception as e:
                    text += f"\n--- Page {page_num + 1} (Error extracting) ---\n"
        
        return {
            "text": text.strip(),
            "pages": page_count,
            "characters": len(text.strip())
        }
    
    except ocrmypdf.exceptions.PriorOcrFoundError:
        # PDF already has OCR, just extract text
        try:
            text = ""
            with open(input_path, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                page_count = len(pdf_reader.pages)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- Page {page_num + 1} ---\n"
                        text += page_text
            
            return {
                "text": text.strip(),
                "pages": page_count,
                "characters": len(text.strip()),
                "note": "PDF already contained searchable text"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Text extraction failed: {str(e)}")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {str(e)}")
    
    finally:
        # Cleanup temporary files
        if input_path.exists():
            input_path.unlink()
        if output_path.exists():
            output_path.unlink()

# Add cleanup endpoint
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
        return {"message": f"Cleaned up {count} temporary files"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")
