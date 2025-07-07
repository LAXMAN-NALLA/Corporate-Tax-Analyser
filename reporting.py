# reporting.py (Corrected Final Version)

import io
import pandas as pd
from fpdf import FPDF
from typing import Dict, Any

def _sanitize_text_for_pdf(text: str) -> str:
    """
    Removes or replaces characters that are not supported by the default PDF fonts (latin-1).
    This prevents encoding errors when writing text to the PDF.
    """
    return text.encode('latin-1', 'replace').decode('latin-1')

def _format_currency(amount: float) -> str:
    """A consistent helper to format numbers into a currency string."""
    return f"EUR {amount:,.2f}" if isinstance(amount, (int, float)) else str(amount)

def create_pdf_report(analysis_data: Dict[Any, Any]) -> bytes:
    """
    Generates a professional PDF summary report from the final analysis data.
    """
    summary = analysis_data.get("tax_return_summary", {}).get("breakdown", {})
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    pdf.cell(0, 10, "Corporate Tax Summary Report", 0, 1, 'C')
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(95, 10, "Line Item", 1, 0, 'L')
    pdf.cell(95, 10, "Amount", 1, 1, 'R')
    
    pdf.set_font("Arial", '', 12)
    line_items = [
        ("Revenue", summary.get("Revenue")),
        ("Expenses", summary.get("Expenses")),
        ("Depreciation", summary.get("Depreciation")),
        ("Deductions", summary.get("Deductions")),
    ]
    for label, value in line_items:
        # Sanitize text just in case, although FPDF handles most standard text well.
        safe_label = _sanitize_text_for_pdf(str(label))
        safe_value = _sanitize_text_for_pdf(_format_currency(value))
        pdf.cell(95, 10, safe_label, 1, 0, 'L')
        pdf.cell(95, 10, safe_value, 1, 1, 'R')
        
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(95, 10, "Net Taxable Income", 1, 0, 'L')
    pdf.cell(95, 10, _format_currency(summary.get("Taxable Income")), 1, 1, 'R')
    pdf.cell(95, 10, "Applied Tax Rate", 1, 0, 'L')
    pdf.cell(95, 10, str(summary.get("Applied Tax Rate", "N/A")), 1, 1, 'R')
    pdf.cell(95, 10, "Final Tax Owed", 1, 0, 'L')
    pdf.cell(95, 10, _format_currency(summary.get("Final Tax Owed")), 1, 1, 'R')
    
    pdf.ln(10)
    
    if analysis_data.get("audit_flags"):
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Audit Flags & Notes", 0, 1, 'L')
        pdf.set_font("Arial", 'I', 10)
        for warning in analysis_data.get("audit_flags", []):
            pdf.set_text_color(220, 50, 50)
            safe_warning = _sanitize_text_for_pdf(str(warning))
            pdf.multi_cell(w=190, h=5, txt=f"- {safe_warning}", border=0, align='L')
        pdf.set_text_color(0, 0, 0)

    # *** THIS IS THE FIX ***
    # The pdf.output() method now returns a byte-like object directly.
    # We do NOT need to call .encode() on it anymore.
    return pdf.output()


def create_excel_report(analysis_data: Dict[Any, Any]) -> bytes:
    """Generates a professional Excel summary report."""
    summary = analysis_data.get("tax_return_summary", {}).get("breakdown", {})
    df = pd.DataFrame(summary.items(), columns=["Line Item", "Amount"])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Tax Summary', index=False, startrow=1)
        workbook = writer.book
        worksheet = writer.sheets['Tax Summary']
        header_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter'})
        money_format = workbook.add_format({'num_format': '€#,##0.00'})
        worksheet.merge_range('A1:B1', 'Corporate Tax Summary Report', header_format)
        worksheet.set_row(0, 30)
        worksheet.set_column('A:A', 35)
        worksheet.set_column('B:B', 20, money_format)
    output.seek(0)
    return output.getvalue()