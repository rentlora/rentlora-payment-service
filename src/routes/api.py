from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId
from typing import List
import httpx
from src.models.db import db
from src.config.settings import settings

router = APIRouter()

class PaymentCreateModel(BaseModel):
    booking_id: str
    amount: float
    payment_method: str

class PaymentOutModel(BaseModel):
    id: str
    booking_id: str
    amount: float
    payment_method: str
    status: str
    transaction_date: datetime

class PaymentStatusUpdateModel(BaseModel):
    status: str

def serialize_payment(payment: dict) -> dict:
    payment["id"] = str(payment.pop("_id"))
    return payment

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=PaymentOutModel)
async def process_payment(payment: PaymentCreateModel):
    # Mocking payment processing
    new_payment = payment.model_dump()
    new_payment["status"] = "success" # Assuming mock success
    new_payment["transaction_date"] = datetime.utcnow()
    
    result = await db.db.payments.insert_one(new_payment)
    new_payment["_id"] = result.inserted_id
    
    # INTER-SERVICE COMMUNICATION
    # Notify the booking service that the payment was successful
    async with httpx.AsyncClient() as client:
        try:
            await client.put(
                f"{settings.BOOKING_SERVICE_URL}/api/bookings/{payment.booking_id}/status",
                json={"payment_status": "paid", "status": "confirmed"}
            )
        except Exception as e:
            print(f"Warning: Failed to reach booking service at {settings.BOOKING_SERVICE_URL}. Error: {e}")
            
    return serialize_payment(new_payment)

@router.get("/booking/{booking_id}", response_model=List[PaymentOutModel])
async def get_booking_payments(booking_id: str):
    payments_cursor = db.db.payments.find({"booking_id": booking_id})
    payments = await payments_cursor.to_list(length=100)
    return [serialize_payment(p) for p in payments]

@router.put("/{payment_id}/status")
async def update_payment_status(payment_id: str, update: PaymentStatusUpdateModel):
    if not ObjectId.is_valid(payment_id):
        raise HTTPException(status_code=400, detail="Invalid Payment ID")
        
    result = await db.db.payments.update_one(
        {"_id": ObjectId(payment_id)},
        {"$set": {"status": update.status}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Payment not found")
        
    return {"message": "Payment status updated"}
