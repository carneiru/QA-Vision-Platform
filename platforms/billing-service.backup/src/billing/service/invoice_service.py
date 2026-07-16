from sqlalchemy.orm import Session
from typing import List, Optional
from ..models.invoice import Invoice, InvoiceStatus
from ..schemas.invoice import InvoiceCreate, InvoiceUpdate, Invoice
from datetime import datetime

class InvoiceService:
    @staticmethod
    def get_invoice_by_id(db: Session, invoice_id: str) -> Optional[Invoice]:
        return db.query(Invoice).filter(Invoice.id == invoice_id).first()
    
    @staticmethod
    def get_invoices_by_subscription(db: Session, subscription_id: str, skip: int = 0, limit: int = 100) -> List[Invoice]:
        return db.query(Invoice).filter(Invoice.subscription_id == subscription_id).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_invoices_by_customer(db: Session, customer_id: str, skip: int = 0, limit: int = 100) -> List[Invoice]:
        # This would require a join with subscriptions table in a real implementation
        # For now, we'll return an empty list as we don't have the relationship set up
        return []
    
    @staticmethod
    def create_invoice(db: Session, invoice_in: InvoiceCreate) -> Invoice:
        db_invoice = Invoice(
            number=invoice_in.number,
            amount=invoice_in.amount,
            currency=invoice_in.currency,
            status=invoice_in.status,
            due_date=invoice_in.due_date,
            period_start=invoice_in.period_start,
            period_end=invoice_in.period_end,
            subscription_id=invoice_in.subscription_id
        )
        db.add(db_invoice)
        db.commit()
        db.refresh(db_invoice)
        return db_invoice
    
    @staticmethod
    def update_invoice(db: Session, invoice_id: str, invoice_in: InvoiceUpdate) -> Optional[Invoice]:
        db_invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if db_invoice:
            update_data = invoice_in.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_invoice, field, value)
            db.commit()
            db.refresh(db_invoice)
        return db_invoice
    
    @staticmethod
    def pay_invoice(db: Session, invoice_id: str) -> Optional[Invoice]:
        db_invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if db_invoice and db_invoice.status == InvoiceStatus.OPEN:
            db_invoice.status = InvoiceStatus.PAID
            db_invoice.paid_at = datetime.utcnow()
            db.commit()
            db.refresh(db_invoice)
        return db_invoice
    
    @staticmethod
    def void_invoice(db: Session, invoice_id: str) -> Optional[Invoice]:
        db_invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if db_invoice:
            db_invoice.status = InvoiceStatus.VOID
            db.commit()
            db.refresh(db_invoice)
        return db_invoice
