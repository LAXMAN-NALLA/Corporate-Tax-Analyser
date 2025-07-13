# reporting.py (Final Enhanced Version)

import io
import pandas as pd
from fpdf import FPDF
from typing import Dict, Any

def _sanitize_text_for_pdf(text: str) -> str:
    """Removes or replaces characters that are not supported by the default PDF fonts (latin-1)."""
    if not text: return ""
    return text.encode('latin-1', 'replace').decode('latin-1')

def _format_currency(amount: float) -> str:
    """A consistent helper to format numbers into a currency string."""
    return f"EUR {amount:,.2f}" if isinstance(amount, (int, float)) else str(amount)

def create_pdf_report(analysis_data: Dict[Any, Any]) -> bytes:
    """Generates a professional PDF summary report from the final analysis data."""
    # --- Extract data from the new, more detailed structure ---
    info = analysis_data.get("general_information", {})
    summary = analysis_data.get("tax_return_summary", {}).get("breakdown", {})
    
    pdf = FPDF()
    pdf.add_page()
    
    # --- NEW: Enhanced Header with Company and Year ---
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, _sanitize_text_for_pdf(f"Corporate Tax Report for {info.get('company_name', 'N/A')}") , 0, 1, 'C')
    pdf.set_font("Arial", 'I', 12)
    pdf.cell(0, 10, f"Fiscal Year: {info.get('fiscal_year', 'N/A')}", 0, 1, 'C')
    pdf.ln(10)
    
    # --- Main Breakdown Table ---
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(130, 8, "Line Item", 1, 0, 'L')
    pdf.cell(60, 8, "Amount", 1, 1, 'R')
    
    pdf.set_font("Arial", '', 12)
    line_items = [
        ("Revenue", summary.get("Revenue")),
        ("Expenses", summary.get("Expenses")),
        ("Depreciation", summary.get("Depreciation")),
        ("Deductions", summary.get("Deductions")),
    ]
    for label, value in line_items:
        pdf.cell(130, 8, str(label), 1, 0, 'L')
        pdf.cell(60, 8, _format_currency(value), 1, 1, 'R')
        
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(130, 8, "Net Taxable Income", 1, 0, 'L')
    pdf.cell(60, 8, _format_currency(summary.get("Taxable Income")), 1, 1, 'R')
    pdf.cell(130, 8, "Applied Tax Rate", 1, 0, 'L')
    pdf.cell(60, 8, str(summary.get("Applied Tax Rate", "N/A")), 1, 1, 'R')
    pdf.cell(130, 8, "Final Tax Owed", 1, 0, 'L')
    pdf.cell(60, 8, _format_currency(summary.get("Final Tax Owed")), 1, 1, 'R')
    
    pdf.ln(10)
    
    # --- Warnings/Audit Flags Section ---
    if analysis_data.get("audit_flags"):
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Audit Flags & Notes", 0, 1, 'L')
        pdf.set_font("Arial", 'I', 10)
        for warning in analysis_data.get("audit_flags", []):
            pdf.set_text_color(220, 50, 50)
            safe_warning = _sanitize_text_for_pdf(str(warning))
            pdf.multi_cell(w=190, h=5, txt=f"- {safe_warning}", border=0, align='L')
        pdf.set_text_color(0, 0, 0)

    return pdf.output()


def create_excel_report(analysis_data: Dict[Any, Any]) -> bytes:
    """Generates a multi-sheet Excel summary report with all the new data."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        
        # --- Sheet 1: Tax Summary ---
        summary_data = analysis_data.get("tax_return_summary", {}).get("breakdown", {})
        df_summary = pd.DataFrame(summary_data.items(), columns=["Line Item", "Value"])
        df_summary.to_excel(writer, sheet_name='Tax Summary', index=False, startrow=1)
        
        # --- NEW: Sheet 2: File Processing Log ---
        metadata = analysis_data.get("file_metadata", [])
        if metadata:
            df_meta = pd.DataFrame(metadata)
            df_meta.to_excel(writer, sheet_name='File Processing Log', index=False)
            worksheet_meta = writer.sheets['File Processing Log']
            worksheet_meta.set_column('A:D', 30)

        # --- NEW: Sheet 3: Audit Flags ---
        audit_flags = analysis_data.get("audit_flags", [])
        if audit_flags:
            df_flags = pd.DataFrame(audit_flags, columns=["Audit Flags & Notes"])
            df_flags.to_excel(writer, sheet_name='Audit Flags', index=False)
            worksheet_flags = writer.sheets['Audit Flags']
            worksheet_flags.set_column('A:A', 80)
        
        # Apply some formatting to the main summary sheet
        workbook = writer.book
        worksheet_summary = writer.sheets['Tax Summary']
        header_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter'})
        worksheet_summary.merge_range('A1:B1', 'Corporate Tax Summary Report', header_format)
        worksheet_summary.set_row(0, 30)
        worksheet_summary.set_column('A:A', 35)
        worksheet_summary.set_column('B:B', 20)

    output.seek(0)
    return output.getvalue()
