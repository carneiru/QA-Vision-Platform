from fastapi import APIRouter
from .endpoints import subscription, invoice, payment_method, webhooks

api_router = APIRouter()

api_router.include_router(subscription.router, prefix="/subscriptions", tags=["subscriptions"])
api_router.include_router(invoice.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(payment_method.router, prefix="/payment-methods", tags=["payment-methods"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

__all__ = ["api_router"]
