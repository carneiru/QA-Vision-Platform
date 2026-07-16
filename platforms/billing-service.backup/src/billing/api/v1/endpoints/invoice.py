from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ....db.session import get_db
from ....models.invoice import Invoice
from ....service.invoice_service import InvoiceService
from ....schemas.invoice import InvoiceCreate, InvoiceUpdate, Invoice

router = APIRouter()

@router.post("/", response_model=Invoice, status_code=status.HTTP_201_CREATED)
def create_invoice(
    invoice_in: InvoiceCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new invoice.
    """
    return InvoiceService.create_invoice(db=db, invoice_in=invoice_in)

@router.get("/", response_model=List[Invoice])
def read_invoices(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve invoices.
    """
    invoices = db.query(Invoice).offset(skip).limit(limit).all()
    return invoices

@router.get("/{invoice_id}", response_model=Invoice)
def read_invoice(
    invoice_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific invoice by ID.
    """
    invoice = InvoiceService.get_invoice_by_id(db=db, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice

@router.put("/{invoice_id}", response_model=Invoice)
def update_invoice(
    invoice_id: str,
    invoice_in: InvoiceUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an invoice.
    """
    invoice = InvoiceService.update_invoice(
        db=db, invoice_id=invoice_id, invoice_in=invoice_in
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice

@router.delete("/{invoice_id}", response_model=Invoice)
def delete_invoice(
    invoice_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete an invoice.
    """
    # In a real system, we might not actually delete but mark as void
    invoice = InvoiceService.get_invoice_by_id(db=db, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    db.delete(invoice)
    db.commit()
    return invoice

@router.post("/{invoice_id}/pay", response_model=Invoice)
def pay_invoice(
    invoice_id: str,
    db: Session = Depends(get_db)
):
    """
    Pay an invoice.
    """
    invoice = InvoiceService.pay_invoice(db=db, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found or cannot be paid")
    return invoice

@router.post("/{invoice_id}/void", response_model=Invoice)
def void_invoice(
    invoice_id: str,
    db: Session = Depends(get_db)
):
    """
    Void an invoice.
    """
    invoice = InvoiceService.void_invoice(db=db, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice
