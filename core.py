# core.py (Intelligent Document Sorter Version)

# --- Standard Library Imports ---
import os
import io
import json
import time
import traceback

# --- Third-Party Library Imports ---
import pdfplumber
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict, Any, List

# --- 1. Configuration and Initialization ---
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- 2. AI Prompts for the Multi-Step Process ---

# Prompt to classify each document first. This is the "sorting hat".
CLASSIFICATION_PROMPT = """
Analyze the first page of the following financial document text. Your ONLY task is to classify the document type.
Respond with a single category from this list: ["P&L_OR_ANNUAL_REPORT", "DEPRECIATION_SCHEDULE", "DEDUCTIONS_DOCUMENT", "OTHER"].
Return ONLY a valid JSON object with one key: {"document_type": "CATEGORY_HERE"}
"""

# Prompt for the main analysis on primary documents.
HOLISTIC_ANALYSIS_PROMPT = """
Analyze the provided financial statement text (from a P&L or Annual Report). Your task is to extract the main financial figures for the entire period.
Prioritize pre-calculated totals for 'Total Revenue', 'Total Expenses', and 'Total Depreciation'.
Return ONLY a valid JSON object: {"revenue": 0.0, "expenses": 0.0, "depreciation": 0.0}
"""

# Targeted prompts for specific override documents.
DEPRECIATION_OVERRIDE_PROMPT = 'Analyze this document, which is a depreciation schedule. Your ONLY task is to find the single, final "Total Depreciation" or "Amortization" figure. Return a single JSON object: {"figure": 12345.67}.'
DEDUCTIONS_OVERRIDE_PROMPT = 'Analyze this document. Your ONLY task is to find the total sum of all "Tax-Deductible Items" or "Tax Credits". Return a single JSON object: {"figure": 12345.67}.'


# --- 3. Helper Functions ---

def _parse_document_content(content: bytes, filename: str) -> str:
    """Extracts all text from a supported document type (PDF, Excel, CSV)."""
    full_text, filename = "", filename.lower()
    if filename.endswith(".pdf"):
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages: full_text += page.extract_text(x_tolerance=1) or "" + "\n"
    elif filename.endswith((".csv", ".xls", ".xlsx")):
        df = pd.read_excel(io.BytesIO(content)) if 'xls' in filename else pd.read_csv(io.BytesIO(content))
        full_text = df.to_string()
    return full_text

def _run_ai_extraction(text: str, prompt: str) -> Dict[str, Any]:
    """A generic helper to run any prompt against provided text, with retries."""
    for attempt in range(3): # Try up to 3 times
        try:
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text[:32000]}],
                temperature=0,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content.strip())
        except Exception as e:
            print(f"ERROR: AI extraction attempt {attempt + 1} failed: {e}")
            if attempt == 2: return {"error": str(e)} # Return error on last attempt
            time.sleep(3) # Wait before retrying
    return {"error": "AI extraction failed after all retries."}


# --- 4. The Main Orchestrator Function ---

def run_intelligent_sorter_analysis(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Orchestrates the new "Intelligent Sorter" pipeline.
    It classifies documents first, then performs a hierarchical analysis.
    """
    # --- Step 1: Classify each uploaded document ---
    print("INFO: Starting document classification...")
    classified_docs = {
        'P&L_OR_ANNUAL_REPORT': [],
        'DEPRECIATION_SCHEDULE': [],
        'DEDUCTIONS_DOCUMENT': []
    }
    source_files = [doc['filename'] for doc in files]

    for doc in files:
        text = _parse_document_content(doc['content'], doc['filename'])
        if not text: continue # Skip empty files

        # Use only the first ~1500 chars for fast and cheap classification.
        classification_result = _run_ai_extraction(text[:1500], CLASSIFICATION_PROMPT)
        doc_type = classification_result.get("document_type", "OTHER")
        print(f"INFO: Classified '{doc['filename']}' as '{doc_type}'")
        
        # Add the full text and filename to the correct "pile".
        if doc_type in classified_docs:
            classified_docs[doc_type].append({'text': text, 'filename': doc['filename']})

    # --- Step 2: Holistic Analysis on Primary Documents ---
    primary_docs = classified_docs['P&L_OR_ANNUAL_REPORT']
    if not primary_docs:
        return {"error": "Analysis failed. No primary financial document (like a P&L or Annual Report) was found in the uploads."}

    # Combine text from all primary documents into a single block for one efficient AI call.
    holistic_text = "\n\n--- END OF DOCUMENT ---\n\n".join([doc['text'] for doc in primary_docs])
    holistic_data = _run_ai_extraction(holistic_text, HOLISTIC_ANALYSIS_PROMPT)
    if "error" in holistic_data: return {"error": f"Holistic analysis failed: {holistic_data['error']}"}

    revenue = float(holistic_data.get("revenue") or 0.0)
    expenses = float(holistic_data.get("expenses") or 0.0)
    depreciation = float(holistic_data.get("depreciation") or 0.0)
    print(f"INFO: Initial holistic results - Revenue: {revenue}, Expenses: {expenses}, Depreciation: {depreciation}")

    # --- Step 3: Process Overrides from specific documents ---
    if classified_docs['DEPRECIATION_SCHEDULE']:
        print("INFO: Processing depreciation override documents...")
        # Use the first document classified as a depreciation schedule as the definitive source.
        dep_doc = classified_docs['DEPRECIATION_SCHEDULE'][0]
        override_data = _run_ai_extraction(dep_doc['text'], DEPRECIATION_OVERRIDE_PROMPT)
        new_dep_val = override_data.get("figure", depreciation)
        depreciation = float(new_dep_val or 0.0) # Override the holistic value.
        print(f"INFO: Depreciation value overridden to: {depreciation}")

    deductions = 0.0
    if classified_docs['DEDUCTIONS_DOCUMENT']:
        print("INFO: Processing deductions documents...")
        # Sum up deductions from all documents classified for this purpose.
        for ded_doc in classified_docs['DEDUCTIONS_DOCUMENT']:
            override_data = _run_ai_extraction(ded_doc['text'], DEDUCTIONS_OVERRIDE_PROMPT)
            deductions += float(override_data.get("figure", 0.0))
        print(f"INFO: Total deductions calculated as: {deductions}")

    # --- Step 4: Final Calculation & Determine Tax Rate ---
    net_taxable_income = revenue - expenses - depreciation - deductions
    tax_owed, applied_tax_rate = 0.0, "0%"
    if net_taxable_income > 0:
        if net_taxable_income <= 200_000:
            tax_owed = net_taxable_income * 0.19
            applied_tax_rate = "19.0%"
        else:
            tax_owed = (200_000 * 0.19) + ((net_taxable_income - 200_000) * 0.258)
            effective_rate = (tax_owed / net_taxable_income) * 100
            applied_tax_rate = f"Progressive (Effective: {effective_rate:.1f}%)"
    
    # --- Step 5: Structure Final Report ---
    final_report = {
        "tax_return_summary": {
            "breakdown": {
                "Revenue": revenue, "Expenses": expenses, "Depreciation": depreciation,
                "Deductions": deductions, "Taxable Income": net_taxable_income,
                "Applied Tax Rate": applied_tax_rate, "Final Tax Owed": max(0, tax_owed)
            }
        },
        "source_files": sorted(list(set(source_files))),
        "audit_flags": []
    }
    
    # --- Step 6: Add Audit Flags ---
    if depreciation == 0.0 and not classified_docs['DEPRECIATION_SCHEDULE']:
        final_report["audit_flags"].append("⚠️ Depreciation not found and no specific schedule was provided. Assumed to be zero.")

    return final_report