"""
Invoice PDF generation utility using ReportLab.

Generates professional invoices with company header, customer details,
itemized table, and grand total.
"""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def generate_invoice_pdf(invoice):
    """Generate a professional PDF invoice.

    Args:
        invoice: An Invoice model instance with related order and order items.

    Returns:
        io.BytesIO buffer containing the rendered PDF.
    """
    buffer = io.BytesIO()
    width, height = A4
    c = canvas.Canvas(buffer, pagesize=A4)

    # ── Colours ───────────────────────────────────────────────────────
    primary = colors.HexColor('#1a237e')
    accent = colors.HexColor('#283593')
    light_bg = colors.HexColor('#e8eaf6')
    dark_text = colors.HexColor('#212121')
    grey_text = colors.HexColor('#757575')

    # ── Company Header ────────────────────────────────────────────────
    c.setFillColor(primary)
    c.rect(0, height - 80, width, 80, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 20)
    c.drawString(30, height - 45, 'Inventory & Order Management System')
    c.setFont('Helvetica', 10)
    c.drawString(30, height - 65, 'Your Trusted Multi-Vendor Inventory Partner')

    # ── Invoice Title ─────────────────────────────────────────────────
    y = height - 110
    c.setFillColor(dark_text)
    c.setFont('Helvetica-Bold', 16)
    c.drawString(30, y, 'INVOICE')
    c.setFont('Helvetica', 10)
    c.setFillColor(grey_text)
    c.drawRightString(width - 30, y, f'Date: {invoice.issued_at.strftime("%d %b %Y")}')

    # ── Invoice & Order Info ──────────────────────────────────────────
    y -= 30
    c.setFillColor(dark_text)
    c.setFont('Helvetica-Bold', 10)
    c.drawString(30, y, 'Invoice No:')
    c.setFont('Helvetica', 10)
    c.drawString(110, y, str(invoice.invoice_number))

    c.setFont('Helvetica-Bold', 10)
    c.drawString(300, y, 'Order No:')
    c.setFont('Helvetica', 10)
    c.drawString(370, y, str(invoice.order.order_number))

    # ── Customer Details ──────────────────────────────────────────────
    y -= 35
    c.setFillColor(light_bg)
    c.rect(25, y - 15, width - 50, 45, fill=True, stroke=False)
    c.setFillColor(dark_text)
    c.setFont('Helvetica-Bold', 10)
    c.drawString(35, y + 15, 'Bill To:')
    c.setFont('Helvetica', 10)
    c.drawString(35, y, f'{invoice.customer_name}')
    c.drawString(35, y - 12, f'{invoice.customer_email}')

    # ── Items Table Header ────────────────────────────────────────────
    y -= 55
    c.setFillColor(accent)
    c.rect(25, y - 5, width - 50, 22, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(35, y + 2, '#')
    c.drawString(60, y + 2, 'Product')
    c.drawString(300, y + 2, 'Qty')
    c.drawString(370, y + 2, 'Unit Price')
    c.drawRightString(width - 35, y + 2, 'Total')

    # ── Items Rows ────────────────────────────────────────────────────
    y -= 22
    c.setFont('Helvetica', 9)
    items = invoice.order.items.select_related('product').all()
    for idx, item in enumerate(items, start=1):
        if y < 100:
            c.showPage()
            y = height - 50
        row_color = light_bg if idx % 2 == 0 else colors.white
        c.setFillColor(row_color)
        c.rect(25, y - 5, width - 50, 18, fill=True, stroke=False)

        c.setFillColor(dark_text)
        c.drawString(35, y + 1, str(idx))
        c.drawString(60, y + 1, str(item.product.name)[:45])
        c.drawString(300, y + 1, str(item.quantity))
        c.drawString(370, y + 1, f'\u20b9{item.unit_price:,.2f}')
        line_total = item.quantity * item.unit_price
        c.drawRightString(width - 35, y + 1, f'\u20b9{line_total:,.2f}')
        y -= 18

    # ── Grand Total ───────────────────────────────────────────────────
    y -= 15
    c.setStrokeColor(primary)
    c.setLineWidth(1.5)
    c.line(300, y + 8, width - 30, y + 8)

    c.setFont('Helvetica-Bold', 12)
    c.setFillColor(primary)
    c.drawString(370, y - 8, 'Grand Total:')
    c.drawRightString(width - 35, y - 8, f'\u20b9{invoice.total_amount:,.2f}')

    # ── Footer ────────────────────────────────────────────────────────
    c.setFillColor(grey_text)
    c.setFont('Helvetica-Oblique', 9)
    c.drawCentredString(width / 2, 50, 'Thank you for your business!')
    c.setFont('Helvetica', 7)
    c.drawCentredString(
        width / 2, 35,
        'This is a computer-generated invoice and does not require a signature.',
    )

    c.save()
    buffer.seek(0)
    return buffer
