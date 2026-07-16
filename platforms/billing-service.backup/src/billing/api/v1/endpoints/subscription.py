from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ....db.session import get_db
from ....models.subscription import Subscription
from ....service.subscription_service import SubscriptionService
from ....schemas.subscription import SubscriptionCreate, SubscriptionUpdate, Subscription

router = APIRouter()

@router.post("/", response_model=Subscription, status_code=status.HTTP_201_CREATED)
def create_subscription(
    subscription_in: SubscriptionCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new subscription.
    """
    return SubscriptionService.create_subscription(db=db, subscription_in=subscription_in)

@router.get("/", response_model=List[Subscription])
def read_subscriptions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve subscriptions.
    """
    subscriptions = db.query(Subscription).offset(skip).limit(limit).all()
    return subscriptions

@router.get("/{subscription_id}", response_model=Subscription)
def read_subscription(
    subscription_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific subscription by ID.
    """
    subscription = SubscriptionService.get_subscription_by_id(db=db, subscription_id=subscription_id)
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription

@router.put("/{subscription_id}", response_model=Subscription)
def update_subscription(
    subscription_id: str,
    subscription_in: SubscriptionUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a subscription.
    """
    subscription = SubscriptionService.update_subscription(
        db=db, subscription_id=subscription_id, subscription_in=subscription_in
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription

@router.delete("/{subscription_id}", response_model=Subscription)
def delete_subscription(
    subscription_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a subscription.
    """
    subscription = SubscriptionService.cancel_subscription(
        db=db, subscription_id=subscription_id
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription

@router.post("/{subscription_id}/renew", response_model=Subscription)
def renew_subscription(
    subscription_id: str,
    db: Session = Depends(get_db)
):
    """
    Renew a subscription.
    """
    # For simplicity, we're just extending the end date
    subscription = SubscriptionService.get_subscription_by_id(
        db=db, subscription_id=subscription_id
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # In a real implementation, we would calculate the new period based on the plan
    from datetime import timedelta
    subscription.current_period_start = subscription.current_period_end
    subscription.current_period_end = subscription.current_period_end + timedelta(days=30)
    subscription.cancel_at_period_end = False
    
    db.commit()
    db.refresh(subscription)
    return subscription

@router.post("/{subscription_id}/pause", response_model=Subscription)
def pause_subscription(
    subscription_id: str,
    db: Session = Depends(get_db)
):
    """
    Pause a subscription.
    """
    subscription = SubscriptionService.get_subscription_by_id(
        db=db, subscription_id=subscription_id
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    subscription.status = "paused"
    db.commit()
    db.refresh(subscription)
    return subscription

@router.post("/{subscription_id}/resume", response_model=Subscription)
def resume_subscription(
    subscription_id: str,
    db: Session = Depends(get_db)
):
    """
    Resume a paused subscription.
    """
    subscription = SubscriptionService.get_subscription_by_id(
        db=db, subscription_id=subscription_id
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Assuming it was paused, we'll set it back to active
    # In a real system, we would store the previous state
    subscription.status = "active"
    db.commit()
    db.refresh(subscription)
    return subscription
