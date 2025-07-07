# api.py (Corrected and Final Version)

import io
from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from core import run_intelligent_sorter_analysis
from reporting import create_pdf_report, create_excel_report

# --- Initialization and CORS ---
app = FastAPI(title="Intelligent Document Sorter Tax API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/analyze-intelligent", summary="Analyze a pool of financial documents with auto-classification")
async def analyze_intelligent_endpoint(
    documents: List[UploadFile] = File(..., description="Upload all relevant financial documents for the year")
):
    """
    Accepts a list of documents, intelligently classifies each one,
    and performs a hierarchical analysis.
    """
    if not documents:
        raise HTTPException(status_code=400, detail="No files were uploaded.")
    files_to_process = [{'content': await f.read(), 'filename': f.filename} for f in documents]
    result = run_intelligent_sorter_analysis(files_to_process)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@app.post("/generate-report/pdf", summary="Generate a PDF summary report")
async def generate_pdf_endpoint(request: Request):
    """Takes the JSON analysis data and returns a downloadable PDF report."""
    analysis_data = await request.json()
    pdf_bytes = create_pdf_report(analysis_data)
    
    # Wrap the bytes in an in-memory stream for robust handling.
    pdf_stream = io.BytesIO(pdf_bytes)
    
    headers = {"Content-Disposition": "attachment; filename=tax_summary_report.pdf"}
    return StreamingResponse(pdf_stream, media_type="application/pdf", headers=headers)

@app.post("/generate-report/excel", summary="Generate an Excel summary report")
async def generate_excel_endpoint(request: Request):
    """Takes the JSON analysis data and returns a downloadable Excel report."""
    analysis_data = await request.json()
    excel_bytes = create_excel_report(analysis_data)
    
    # Apply the same robust streaming pattern for consistency.
    excel_stream = io.BytesIO(excel_bytes)
    
    headers = {"Content-Disposition": "attachment; filename=tax_summary_report.xlsx"}
    return StreamingResponse(excel_stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)

@app.get("/", summary="API Health Check")
def read_root():
    """A simple endpoint to confirm that the API is running."""
    return {"status": "Intelligent Tax Analyzer API is running"}