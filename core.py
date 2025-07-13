# core.py (Final Production-Grade Version)

# --- Standard Library Imports ---
import os, io, json, time, traceback, re

# --- Third-Party Library Imports ---
import pandas as pd, pdfplumber
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict, Any, List

# --- 1. Configuration and Initialization ---
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- 2. AI Prompts (Final, User-Refined Versions) ---

# This prompt is for the initial, fast classification of each document.
CLASSIFICATION_PROMPT = """
You are a Dutch corporate finance document classification assistant.

Analyze the **first page** of the given financial document text and extract the following fields:

1. **Document Type**: Classify the document into one of these:
   - "P&L_OR_ANNUAL_REPORT"
   - "DEPRECIATION_SCHEDULE"
   - "DEDUCTIONS_DOCUMENT"
   - "OTHER"

2. **Company Name**: Extract the full legal entity name (e.g., "XYZ Holding B.V." or "Acme Corp N.V.").
   - If not found, return: "Unknown Company"

3. **Fiscal Year**: Extract the 4-digit year this document primarily applies to (e.g., 2023).
   - This could be found in headings, footers, metadata, or report sections.
   - If not found, return: "Unknown Year"

Return ONLY a valid JSON object with this exact format:
{
  "document_type": "CATEGORY_HERE",
  "company_name": "Company Name B.V.",
  "fiscal_year": "YYYY"
}
"""

# This prompt performs the main analysis on primary documents.
HOLISTIC_ANALYSIS_PROMPT = """
Analyze the provided financial statement text (from a P&L or Annual Report). Your task is to extract the main financial figures for the entire period.

**CRITICAL INSTRUCTIONS:**
1. Find the final and overall 'Total Revenue' or 'Sales' figure.
2. For 'Total Expenses', prioritize a pre-calculated value (e.g., 'Total Expenses' or 'Operating Costs'). DO NOT sum individual lines if a total is shown.
3. For 'Depreciation', use the value only if explicitly mentioned (e.g., "Total Depreciation" or "Amortization").
4. DO NOT estimate or assume values if they are not explicitly stated.

Return ONLY a valid JSON object:
{
  "revenue": 0.0,
  "expenses": 0.0,
  "depreciation": 0.0
}
"""

# These prompts are for specific, targeted overrides.
DEPRECIATION_OVERRIDE_PROMPT = 'Analyze this document, which is a depreciation schedule. Your ONLY task is to find the single, final "Total Depreciation" or "Amortization" figure. Return a single JSON object: {"figure": 12345.67}.'
DEDUCTIONS_OVERRIDE_PROMPT = 'Analyze this document. Your ONLY task is to find the total sum of all "Tax-Deductible Items" or "Tax Credits". Return a single JSON object: {"figure": 12345.67}.'


# --- 3. Helper Functions ---

def _normalize_company_name(name: str) -> str:
    """A simple normalizer to handle variations like 'B.V.' vs 'BV' for accurate comparison."""
    if not isinstance(name, str) or name == "Unknown Company": return "unknown"
    return re.sub(r'[\.,]', '', name.lower()).replace("b v", "bv").replace("n v", "nv").strip()

def _parse_document_content(content: bytes, filename: str) -> str:
    """Extracts all text from a supported document type."""
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
    for attempt in range(3):
        try:
            response = client.chat.completions.create(model="gpt-4-turbo", messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text[:32000]}], temperature=0, response_format={"type": "json_object"})
            return json.loads(response.choices[0].message.content.strip())
        except Exception as e:
            print(f"ERROR: AI extraction attempt {attempt + 1} failed: {e}")
            if attempt == 2: return {"error": str(e)}
            time.sleep(3)
    return {"error": "AI extraction failed after all retries."}


# --- 4. The Main Orchestrator Function ---
def run_intelligent_sorter_analysis(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Orchestrates the "Intelligent Sorter" pipeline with company and fiscal year validation."""
    classified_docs = {'P&L_OR_ANNUAL_REPORT': [], 'DEPRECIATION_SCHEDULE': [], 'DEDUCTIONS_DOCUMENT': []}
    company_names, fiscal_years, file_metadata = set(), set(), []

    # Step 1: Classify each document and extract metadata
    for doc in files:
        text = _parse_document_content(doc['content'], doc['filename'])
        if not text: continue
        
        classification_result = _run_ai_extraction(text[:2500], CLASSIFICATION_PROMPT)
        doc_type = classification_result.get("document_type", "OTHER")
        company_name = classification_result.get("company_name")
        fiscal_year = classification_result.get("fiscal_year")
        
        file_metadata.append({"filename": doc['filename'], "type": doc_type, "company_name_detected": company_name, "fiscal_year_detected": fiscal_year})
        if company_name and company_name != "Unknown Company": company_names.add(_normalize_company_name(company_name))
        if fiscal_year and fiscal_year != "Unknown Year": fiscal_years.add(str(fiscal_year))
        
        if doc_type in classified_docs:
            classified_docs[doc_type].append({'text': text, 'filename': doc['filename']})

    # Step 1.5: CRITICAL VALIDATION CHECKS
    if len(company_names) > 1: return {"error": f"Analysis failed. Documents from multiple companies were detected: {list(company_names)}. Please upload documents for only one company."}
    if len(fiscal_years) > 1: return {"error": f"Analysis failed. Documents from multiple fiscal years were detected: {list(fiscal_years)}. Please upload documents for a single year only."}

    final_company_name = list(company_names)[0].title() if company_names else "Unknown Company"
    final_fiscal_year = list(fiscal_years)[0] if fiscal_years else "Unknown Year"

    # Step 2 & 3: Holistic Analysis and Overrides
    primary_docs = classified_docs['P&L_OR_ANNUAL_REPORT']
    if not primary_docs: return {"error": "Analysis failed. No primary financial document (P&L or Annual Report) was found."}
    
    holistic_text = "\n\n--- END OF DOCUMENT ---\n\n".join([doc['text'] for doc in primary_docs])
    holistic_data = _run_ai_extraction(holistic_text, HOLISTIC_ANALYSIS_PROMPT)
    if "error" in holistic_data: return {"error": f"Holistic analysis failed: {holistic_data['error']}"}

    revenue, expenses, depreciation = float(holistic_data.get("revenue") or 0.0), float(holistic_data.get("expenses") or 0.0), float(holistic_data.get("depreciation") or 0.0)
    audit_flags = []
    
    if classified_docs['DEPRECIATION_SCHEDULE']:
        dep_doc = classified_docs['DEPRECIATION_SCHEDULE'][0]
        override_data = _run_ai_extraction(dep_doc['text'], DEPRECIATION_OVERRIDE_PROMPT)
        new_dep_val = override_data.get("figure", depreciation)
        depreciation = float(new_dep_val or 0.0)
        audit_flags.append(f"ℹ️ Depreciation value of {depreciation:,.2f} was taken from override document: {dep_doc['filename']}")

    deductions = 0.0
    if classified_docs['DEDUCTIONS_DOCUMENT']:
        for ded_doc in classified_docs['DEDUCTIONS_DOCUMENT']:
            override_data = _run_ai_extraction(ded_doc['text'], DEDUCTIONS_OVERRIDE_PROMPT)
            deductions += float(override_data.get("figure", 0.0))
        audit_flags.append(f"ℹ️ Deductions of {deductions:,.2f} were calculated from supplemental document(s).")

    # Step 4 & 5: Final Calculation and Reporting
    net_taxable_income = revenue - expenses - depreciation - deductions
    tax_owed, applied_tax_rate = 0.0, "0%"
    if net_taxable_income > 0:
        if net_taxable_income <= 200_000: tax_owed, applied_tax_rate = net_taxable_income * 0.19, "19.0%"
        else:
            tax_owed = (200_000 * 0.19) + ((net_taxable_income - 200_000) * 0.258)
            effective_rate = (tax_owed / net_taxable_income) * 100
            applied_tax_rate = f"Progressive (Effective: {effective_rate:.1f}%)"
    
    if depreciation == 0.0 and not classified_docs['DEPRECIATION_SCHEDULE']: audit_flags.append("⚠️ Depreciation not found and no specific schedule was provided. Assumed to be zero.")

    return {
        "general_information": {"company_name": final_company_name, "fiscal_year": final_fiscal_year},
        "tax_return_summary": {
            "breakdown": {
                "Revenue": revenue, "Expenses": expenses, "Depreciation": depreciation,
                "Deductions": deductions, "Taxable Income": net_taxable_income,
                "Applied Tax Rate": applied_tax_rate, "Final Tax Owed": max(0, tax_owed)
            }
        },
        "file_metadata": file_metadata,
        "audit_flags": audit_flags
    }
