from sqlalchemy.orm import Session
from typing import List, Optional
from ..models.subscription import Subscription, SubscriptionStatus
from ..schemas.subscription import SubscriptionCreate, SubscriptionUpdate, Subscription

class SubscriptionService:
    @staticmethod
    def get_subscription_by_id(db: Session, subscription_id: str) -> Optional[Subscription]:
        return db.query(Subscription).filter(Subscription.id == subscription_id).first()
    
    @staticmethod
    def get_subscriptions_by_customer(db: Session, customer_id: str, skip: int = 0, limit: int = 100) -> List[Subscription]:
        return db.query(Subscription).filter(Subscription.customer_id == customer_id).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_subscriptions_by_organization(db: Session, organization_id: str, skip: int = 0, limit: int = 100) -> List[Subscription]:
        return db.query(Subscription).filter(Subscription.organization_id == organization_id).offset(skip).limit(limit).all()
    
    @staticmethod
    def create_subscription(db: Session, subscription_in: SubscriptionCreate) -> Subscription:
        db_subscription = Subscription(
            plan_id=subscription_in.plan_id,
            customer_id=subscription_in.customer_id,
            organization_id=subscription_in.organization_id,
            status=subscription_in.status,
            current_period_start=subscription_in.current_period_start,
            current_period_end=subscription_in.current_period_end,
            trial_start=subscription_in.trial_start,
            trial_end=subscription_in.trial_end,
            cancel_at_period_end=subscription_in.cancel_at_period_end
        )
        db.add(db_subscription)
        db.commit()
        db.refresh(db_subscription)
        return db_subscription
    
    @staticmethod
    def update_subscription(db: Session, subscription_id: str, subscription_in: SubscriptionUpdate) -> Optional[Subscription]:
        db_subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if db_subscription:
            update_data = subscription_in.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_subscription, field, value)
            db.commit()
            db.refresh(db_subscription)
        return db_subscription
    
    @staticmethod
    def cancel_subscription(db: Session, subscription_id: str) -> Optional[Subscription]:
        db_subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if db_subscription:
            db_subscription.status = SubscriptionStatus.CANCELED
            db.commit()
            db.refresh(db_subscription)
        return db_subscription
    
    @staticmethod
    def pause_subscription(db: Session, subscription_id: str) -> Optional[Subscription]:
        db_subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if db_subscription:
            db_subscription.status = SubscriptionStatus.PAUSED
            db.commit()
            db.refresh(db_subscription)
        return db_subscription
    
    @staticmethod
    def resume_subscription(db: Session, subscription_id: str) -> Optional[Subscription]:
        db_subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if db_subscription and db_subscription.status == SubscriptionStatus.PAUSED:
            # In a real implementation, we would restore the previous status
            db_subscription.status = SubscriptionStatus.ACTIVE
            db.commit()
            db.refresh(db_subscription)
        return db_subscription
    
    @staticmethod
    def renew_subscription(db: Session, subscription_id: str) -> Optional[Subscription]:
        db_subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if db_subscription:
            # In a real implementation, we would extend the period and potentially create a new invoice
            # For now, we'll just mark it as active if it was cancelled
            if db_subscription.status == SubscriptionStatus.CANCELED:
                db_subscription.status = SubscriptionStatus.ACTIVE
                db.commit()
                db.refresh(db_subscription)
        return db_subscription
