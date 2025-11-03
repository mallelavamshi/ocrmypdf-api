from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
import ocrmypdf
import os
import tempfile
import uuid
from pathlib import Path

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
            filename=f"searchable_{file.filename}"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")
    
    finally:
        # Cleanup temporary files
        if input_path.exists():
            input_path.unlink()
        if output_path.exists() and os.path.exists(output_path):
            # Keep file until response is sent
            pass

@app.post("/extract-text")
async def extract_text(file: UploadFile = File(...)):
    """
    Extract text from a scanned PDF
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
        
        # Process with OCRmyPDF to add text layer
        ocrmypdf.ocr(input_path, output_path, force_ocr=True)
        
        # Extract text using pdfminer or similar
        import PyPDF2
        with open(output_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
        
        return {"text": text, "pages": len(pdf_reader.pages)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {str(e)}")
    
    finally:
        if input_path.exists():
            input_path.unlink()
        if output_path.exists():
            output_path.unlink()
