from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ....db.session import get_db
from ....models.payment_method import PaymentMethod
from ....service.payment_method_service import PaymentMethodService
from ....schemas.payment_method import PaymentMethodCreate, PaymentMethodUpdate, PaymentMethod

router = APIRouter()

@router.post("/", response_model=PaymentMethod, status_code=status.HTTP_201_CREATED)
def create_payment_method(
    payment_method_in: PaymentMethodCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new payment method.
    """
    return PaymentMethodService.create_payment_method(db=db, payment_method_in=payment_method_in)

@router.get("/", response_model=List[PaymentMethod])
def read_payment_methods(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve payment methods.
    """
    payment_methods = db.query(PaymentMethod).offset(skip).limit(limit).all()
    return payment_methods

@router.get("/{payment_method_id}", response_model=PaymentMethod)
def read_payment_method(
    payment_method_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific payment method by ID.
    """
    payment_method = PaymentMethodService.get_payment_method_by_id(db=db, payment_method_id=payment_method_id)
    if payment_method is None:
        raise HTTPException(status_code=404, detail="Payment method not found")
    return payment_method

@router.put("/{payment_method_id}", response_model=PaymentMethod)
def update_payment_method(
    payment_method_id: str,
    payment_method_in: PaymentMethodUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a payment method.
    """
    payment_method = PaymentMethodService.update_payment_method(
        db=db, payment_method_id=payment_method_id, payment_method_in=payment_method_in
    )
    if payment_method is None:
        raise HTTPException(status_code=404, detail="Payment method not found")
    return payment_method

@router.delete("/{payment_method_id}", response_model=bool)
def delete_payment_method(
    payment_method_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a payment method.
    """
    result = PaymentMethodService.delete_payment_method(
        db=db, payment_method_id=payment_method_id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Payment method not found")
    return result

@router.post("/{payment_method_id}/set-default", response_model=bool)
def set_default_payment_method(
    payment_method_id: str,
    customer_id: str,  # In a real app, this would come from auth context
    db: Session = Depends(get_db)
):
    """
    Set a payment method as the default for a customer.
    """
    result = PaymentMethodService.set_default_payment_method(
        db=db, customer_id=customer_id, payment_method_id=payment_method_id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Payment method not found")
    return result
