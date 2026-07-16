from sqlalchemy.orm import Session
from typing import List, Optional
from ..models.payment_method import PaymentMethod, PaymentMethodType
from ..schemas.payment_method import PaymentMethodCreate, PaymentMethodUpdate, PaymentMethod

class PaymentMethodService:
    @staticmethod
    def get_payment_method_by_id(db: Session, payment_method_id: str) -> Optional[PaymentMethod]:
        return db.query(PaymentMethod).filter(PaymentMethod.id == payment_method_id).first()
    
    @staticmethod
    def get_payment_methods_by_customer(db: Session, customer_id: str, skip: int = 0, limit: int = 100) -> List[PaymentMethod]:
        return db.query(PaymentMethod).filter(PaymentMethod.customer_id == customer_id).offset(skip).limit(limit).all()
    
    @staticmethod
    def create_payment_method(db: Session, payment_method_in: PaymentMethodCreate) -> PaymentMethod:
        db_payment_method = PaymentMethod(
            customer_id=payment_method_in.customer_id,
            type=payment_method_in.type,
            provider=payment_method_in.provider,
            provider_id=payment_method_in.provider_id,
            last4=payment_method_in.last4,
            brand=payment_method_in.brand,
            exp_month=payment_method_in.exp_month,
            exp_year=payment_method_in.exp_year,
            is_default=payment_method_in.is_default
        )
        db.add(db_payment_method)
        db.commit()
        db.refresh(db_payment_method)
        return db_payment_method
    
    @staticmethod
    def update_payment_method(db: Session, payment_method_id: str, payment_method_in: PaymentMethodUpdate) -> Optional[PaymentMethod]:
        db_payment_method = db.query(PaymentMethod).filter(PaymentMethod.id == payment_method_id).first()
        if db_payment_method:
            update_data = payment_method_in.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_payment_method, field, value)
            db.commit()
            db.refresh(db_payment_method)
        return db_payment_method
    
    @staticmethod
    def delete_payment_method(db: Session, payment_method_id: str) -> bool:
        db_payment_method = db.query(PaymentMethod).filter(PaymentMethod.id == payment_method_id).first()
        if db_payment_method:
            db.delete(db_payment_method)
            db.commit()
            return True
        return False
    
    @staticmethod
    def set_default_payment_method(db: Session, customer_id: str, payment_method_id: str) -> bool:
        # First, unset any existing default payment method for this customer
        db.query(PaymentMethod).filter(
            PaymentMethod.customer_id == customer_id,
            PaymentMethod.is_default == True
        ).update({PaymentMethod.is_default: False})
        
        # Then set the new default
        result = db.query(PaymentMethod).filter(
            PaymentMethod.id == payment_method_id,
            PaymentMethod.customer_id == customer_id
        ).update({PaymentMethod.is_default: True})
        
        db.commit()
        return result > 0
