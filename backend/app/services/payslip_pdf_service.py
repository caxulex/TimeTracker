"""
PDF Payslip Generation Service

Generates professional PDF payslips for employees using ReportLab.
"""

import io
import logging
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.utils.timewindow import now_utc

logger = logging.getLogger(__name__)


class PayslipPDFGenerator:
    """
    Generates professional PDF payslips.

    Usage:
        generator = PayslipPDFGenerator()
        pdf_bytes = generator.generate_payslip(payslip_data)
    """

    def __init__(self, company_name: str = "Time Tracker", company_logo: Optional[str] = None):
        self.company_name = company_name
        self.company_logo = company_logo
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        self.styles.add(ParagraphStyle(
            name='CompanyName',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=6,
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='PayslipTitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#374151'),
            spaceBefore=12,
            spaceAfter=12,
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading3'],
            fontSize=11,
            textColor=colors.HexColor('#1f2937'),
            spaceBefore=12,
            spaceAfter=6,
            borderPadding=4,
            backColor=colors.HexColor('#f3f4f6')
        ))

        self.styles.add(ParagraphStyle(
            name='FieldLabel',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#6b7280')
        ))

        self.styles.add(ParagraphStyle(
            name='FieldValue',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#111827')
        ))

        self.styles.add(ParagraphStyle(
            name='TotalAmount',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=colors.HexColor('#059669'),
            fontName='Helvetica-Bold',
            alignment=TA_RIGHT
        ))

        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#9ca3af'),
            alignment=TA_CENTER
        ))

    def generate_payslip(
        self,
        employee_name: str,
        employee_email: str,
        employee_id: int,
        period_name: str,
        period_start: date,
        period_end: date,
        regular_hours: Decimal,
        overtime_hours: Decimal,
        regular_rate: Decimal,
        overtime_rate: Decimal,
        gross_amount: Decimal,
        adjustments: List[Dict[str, Any]],
        adjustments_total: Decimal,
        net_amount: Decimal,
        currency: str = "USD",
        company_name: Optional[str] = None,
        company_address: Optional[str] = None,
        payment_date: Optional[date] = None,
    ) -> bytes:
        """
        Generate a PDF payslip.

        Returns:
            bytes: PDF file content
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )

        story = []

        # Company Header
        company = company_name or self.company_name
        story.append(Paragraph(company, self.styles['CompanyName']))
        if company_address:
            story.append(Paragraph(company_address, self.styles['Normal']))
        story.append(Spacer(1, 12))

        # Payslip Title
        story.append(Paragraph("PAYSLIP", self.styles['PayslipTitle']))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#e5e7eb')))
        story.append(Spacer(1, 12))

        # Employee and Period Information (side by side)
        info_data = [
            [
                Paragraph("<b>Employee Information</b>", self.styles['FieldValue']),
                Paragraph("<b>Pay Period</b>", self.styles['FieldValue'])
            ],
            [
                Paragraph(f"Name: {employee_name}", self.styles['FieldValue']),
                Paragraph(f"Period: {period_name}", self.styles['FieldValue'])
            ],
            [
                Paragraph(f"Email: {employee_email}", self.styles['FieldValue']),
                Paragraph(f"Start: {period_start.strftime('%B %d, %Y')}", self.styles['FieldValue'])
            ],
            [
                Paragraph(f"Employee ID: {employee_id}", self.styles['FieldValue']),
                Paragraph(f"End: {period_end.strftime('%B %d, %Y')}", self.styles['FieldValue'])
            ],
        ]

        if payment_date:
            info_data.append([
                Paragraph("", self.styles['FieldValue']),
                Paragraph(f"Payment Date: {payment_date.strftime('%B %d, %Y')}", self.styles['FieldValue'])
            ])

        info_table = Table(info_data, colWidths=[3.5*inch, 3.5*inch])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 20))

        # Earnings Section
        story.append(Paragraph("EARNINGS", self.styles['SectionHeader']))

        regular_amount = regular_hours * regular_rate
        overtime_amount = overtime_hours * overtime_rate

        earnings_data = [
            ['Description', 'Hours', 'Rate', 'Amount'],
            ['Regular Hours', f"{regular_hours:.2f}", f"${regular_rate:.2f}", f"${regular_amount:.2f}"],
            ['Overtime Hours', f"{overtime_hours:.2f}", f"${overtime_rate:.2f}", f"${overtime_amount:.2f}"],
            ['', '', 'Gross Pay:', f"${gross_amount:.2f}"],
        ]

        earnings_table = Table(earnings_data, colWidths=[2.5*inch, 1.25*inch, 1.5*inch, 1.75*inch])
        earnings_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#374151')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            # Body rows
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            # Gross pay row
            ('FONTNAME', (2, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (2, -1), (-1, -1), 1, colors.HexColor('#d1d5db')),
            # Grid
            ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        story.append(earnings_table)
        story.append(Spacer(1, 20))

        # Adjustments Section (if any)
        if adjustments:
            story.append(Paragraph("ADJUSTMENTS", self.styles['SectionHeader']))

            adj_data = [['Type', 'Description', 'Amount']]
            for adj in adjustments:
                adj_type = adj.get('adjustment_type', 'adjustment').replace('_', ' ').title()
                adj_desc = adj.get('description', '')[:50]
                adj_amount = adj.get('amount', Decimal('0.00'))
                sign = '+' if adj_amount >= 0 else ''
                adj_data.append([adj_type, adj_desc, f"{sign}${adj_amount:.2f}"])

            adj_data.append(['', 'Total Adjustments:', f"${adjustments_total:.2f}"])

            adj_table = Table(adj_data, colWidths=[1.5*inch, 3.5*inch, 2*inch])
            adj_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#374151')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('FONTNAME', (1, -1), (-1, -1), 'Helvetica-Bold'),
                ('LINEABOVE', (1, -1), (-1, -1), 1, colors.HexColor('#d1d5db')),
                ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#e5e7eb')),
            ]))
            story.append(adj_table)
            story.append(Spacer(1, 20))

        # Net Pay Summary
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1e40af')))
        story.append(Spacer(1, 10))

        net_data = [
            ['', 'NET PAY:', f"${net_amount:.2f} {currency}"],
        ]

        net_table = Table(net_data, colWidths=[3*inch, 2*inch, 2*inch])
        net_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (1, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (1, 0), (1, 0), 12),
            ('FONTSIZE', (2, 0), (2, 0), 16),
            ('TEXTCOLOR', (2, 0), (2, 0), colors.HexColor('#059669')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(net_table)
        story.append(Spacer(1, 30))

        # Footer
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e5e7eb')))
        story.append(Spacer(1, 10))
        story.append(Paragraph(
            f"Generated on {now_utc().strftime('%B %d, %Y at %I:%M %p UTC')}",
            self.styles['Footer']
        ))
        story.append(Paragraph(
            "This is a computer-generated document. No signature is required.",
            self.styles['Footer']
        ))

        # Build PDF
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(f"Generated payslip PDF for employee {employee_id}, period {period_name}")
        return pdf_bytes

    def generate_batch_payslips(
        self,
        payslips_data: List[Dict[str, Any]],
        company_name: Optional[str] = None,
        company_address: Optional[str] = None,
    ) -> Dict[int, bytes]:
        """
        Generate multiple payslips.

        Args:
            payslips_data: List of payslip data dictionaries

        Returns:
            Dict mapping employee_id to PDF bytes
        """
        results = {}
        for data in payslips_data:
            try:
                pdf_bytes = self.generate_payslip(
                    employee_name=data['employee_name'],
                    employee_email=data['employee_email'],
                    employee_id=data['employee_id'],
                    period_name=data['period_name'],
                    period_start=data['period_start'],
                    period_end=data['period_end'],
                    regular_hours=data['regular_hours'],
                    overtime_hours=data['overtime_hours'],
                    regular_rate=data['regular_rate'],
                    overtime_rate=data['overtime_rate'],
                    gross_amount=data['gross_amount'],
                    adjustments=data.get('adjustments', []),
                    adjustments_total=data.get('adjustments_total', Decimal('0.00')),
                    net_amount=data['net_amount'],
                    currency=data.get('currency', 'USD'),
                    company_name=company_name,
                    company_address=company_address,
                    payment_date=data.get('payment_date'),
                )
                results[data['employee_id']] = pdf_bytes
            except Exception as e:
                logger.error(f"Failed to generate payslip for employee {data.get('employee_id')}: {e}")
                raise

        return results


# Singleton instance
payslip_generator = PayslipPDFGenerator()
