"""
QBitFlow Webhook and Redirect Handler Example

This FastAPI server demonstrates how to handle:
1. Webhook notifications from QBitFlow
2. Success redirect URLs
3. Cancel redirect URLs

Run with: uvicorn server:app --reload --port 8001
"""

from fastapi import FastAPI, HTTPException
from qbitflow import QBitFlow
from qbitflow.dto.transaction.session import SessionWebhookResponse
from qbitflow.dto.transaction.status import (
    TransactionStatusValue,
    TransactionType
)

# Initialize FastAPI application
app = FastAPI(
    title="QBitFlow Webhook Handler",
    description="Example webhook and redirect handler for QBitFlow payments",
    version="1.0.0"
)

# Initialize QBitFlow client
# In production, use environment variables for the API key
qbitflow_client = QBitFlow(api_key="<your_api_key_here>")


@app.post("/webhook")
async def handle_webhook(event: SessionWebhookResponse):
    """
    Handle webhook events from QBitFlow.
    
    This endpoint receives notifications when:
    - A payment is completed
    - A subscription is created
    - A payment fails
    - A transaction is cancelled
    
    Args:
        event: The webhook event payload from QBitFlow
    
    Returns:
        Acknowledgment of receipt
    """
    print("=" * 60)
    print("📬 Received webhook event from QBitFlow")
    print("=" * 60)
    
    # Extract event details
    session_uuid = event.uuid
    transaction_status = event.status.status
    transaction_type = event.status.type
    session = event.session
    
    print(f"Session UUID: {session_uuid}")
    print(f"Transaction Type: {transaction_type.value}")
    print(f"Transaction Status: {transaction_status.value}")
    print(f"Product: {session.product_name}")
    print(f"Price: ${session.price} USD")
    print(f"Customer UUID: {session.customer_uuid}")
    
    # Handle different transaction statuses
    if transaction_status == TransactionStatusValue.COMPLETED:
        print("\n✅ PAYMENT COMPLETED SUCCESSFULLY")
        
        # Payment completed - grant access to product/service
        customer_uuid = session.customer_uuid
        product_name = session.product_name
        price = session.price
        
        print(f"\n🎉 Action Items:")
        print(f"  1. Grant access to '{product_name}' for customer {customer_uuid}")
        print(f"  2. Update database with transaction details")
        print(f"  3. Send confirmation email to customer")
        print(f"  4. Log successful payment of ${price}")
        
        # Example: Grant access (implement your business logic here)
        try:
            grant_product_access(customer_uuid, product_name)
            send_confirmation_email(customer_uuid, session)
            log_successful_payment(session_uuid, price)
        except Exception as e:
            print(f"❌ Error processing completed payment: {e}")
        
    elif transaction_status == TransactionStatusValue.FAILED:
        print("\n❌ PAYMENT FAILED")
        
        error_message = event.status.message or "Unknown error"
        print(f"  Error: {error_message}")
        print(f"\n⚠️ Action Items:")
        print(f"  1. Notify customer about failed payment")
        print(f"  2. Log failed transaction for review")
        print(f"  3. Potentially retry or offer alternative payment method")
        
        # Handle failed payment
        try:
            notify_payment_failure(session.customer_uuid, error_message)
            log_failed_payment(session_uuid, error_message)
        except Exception as e:
            print(f"❌ Error handling failed payment: {e}")
    
    elif transaction_status == TransactionStatusValue.CANCELLED:
        print("\n🚫 PAYMENT CANCELLED BY USER")
        print(f"\n📝 Action Items:")
        print(f"  1. Log cancelled transaction")
        print(f"  2. Optionally send reminder email")
        
        try:
            log_cancelled_payment(session_uuid)
        except Exception as e:
            print(f"❌ Error handling cancelled payment: {e}")
    
    elif transaction_status == TransactionStatusValue.PENDING:
        print("\n⏳ PAYMENT PENDING")
        print(f"  Waiting for blockchain confirmation...")
    
    elif transaction_status == TransactionStatusValue.WAITING_CONFIRMATION:
        print("\n⌛ WAITING FOR CONFIRMATION")
        print(f"  Transaction submitted, awaiting confirmation...")
    
    print("=" * 60)
    
    # Return acknowledgment
    return {
        "status": "received",
        "session_uuid": session_uuid,
        "transaction_status": transaction_status.value
    }


@app.get("/success")
async def handle_success(uuid: str, transaction_type: TransactionType):
    """
    Handle success redirect from QBitFlow payment page.
    
    This endpoint is called when a customer completes a payment
    and is redirected back to your application.
    
    Args:
        uuid: The session or transaction UUID
        transaction_type: The type of transaction (payment, subscription, etc.)
    
    Returns:
        Success page data or redirect
    """
    print("=" * 60)
    print("✅ Success redirect received")
    print("=" * 60)
    
    print(f"UUID: {uuid}")
    print(f"Transaction Type: {transaction_type.value}")
    
    try:
        # Fetch the current transaction status
        transaction_status = qbitflow_client.transaction_status.get(
            transaction_uuid=uuid,
            transaction_type=transaction_type
        )
        
        print(f"Current Status: {transaction_status.status.value}")
        
        # Check if the transaction is completed
        if transaction_status.status == TransactionStatusValue.COMPLETED:
            print("\n🎉 Transaction is confirmed!")
            
            # Get session/payment details based on transaction type
            if transaction_type == TransactionType.ONE_TIME_PAYMENT:
                session = qbitflow_client.one_time_payments.get_session(uuid)
                print(f"Payment for: {session.product_name}")
                print(f"Amount: ${session.price} USD")
                
                return {
                    "status": "success",
                    "message": "Payment completed successfully!",
                    "transaction_uuid": uuid,
                    "product": session.product_name,
                    "amount": session.price,
                    "customer_uuid": session.customer_uuid
                }
            
            elif transaction_type == TransactionType.CREATE_SUBSCRIPTION:
                session = qbitflow_client.subscriptions.get_session(uuid)
                print(f"Subscription for: {session.product_name}")
                print(f"Amount: ${session.price} USD")
                
                return {
                    "status": "success",
                    "message": "Subscription created successfully!",
                    "transaction_uuid": uuid,
                    "product": session.product_name,
                    "amount": session.price,
                    "customer_uuid": session.customer_uuid
                }
        
        elif transaction_status.status == TransactionStatusValue.PENDING:
            print("\n⏳ Transaction is still pending...")
            return {
                "status": "pending",
                "message": "Your transaction is being processed. You'll receive a confirmation soon.",
                "transaction_uuid": uuid
            }
        
        else:
            print(f"\n⚠️ Transaction status: {transaction_status.status.value}")
            return {
                "status": transaction_status.status.value,
                "message": f"Transaction is {transaction_status.status.value}",
                "transaction_uuid": uuid
            }
    
    except Exception as e:
        print(f"\n❌ Error fetching transaction status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing success redirect: {str(e)}"
        )


@app.get("/cancel")
async def handle_cancel():
    """
    Handle cancel redirect from QBitFlow payment page.
    
    This endpoint is called when a customer cancels the payment
    and is redirected back to your application.
    
    Returns:
        Cancel page data or redirect
    """
    print("=" * 60)
    print("🚫 Cancel redirect received")
    print("=" * 60)
    
    print("User cancelled the payment")
    
    # Log the cancellation
    # Optionally send reminder email
    # Display cancellation page to user
    
    return {
        "status": "cancelled",
        "message": "Payment was cancelled. You can try again anytime.",
        "action": "redirect_to_pricing"  # Or show retry button
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "QBitFlow Webhook Handler",
        "version": "1.0.0",
        "endpoints": {
            "webhook": "/webhook (POST)",
            "success": "/success (GET)",
            "cancel": "/cancel (GET)"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# =============================================================================
# Helper Functions (Implement your business logic here)
# =============================================================================

def grant_product_access(customer_uuid: str, product_name: str):
    """Grant customer access to the purchased product."""
    # TODO: Implement your logic to grant access
    # Example:
    # - Update user permissions in database
    # - Activate subscription
    # - Enable features
    print(f"[GRANT ACCESS] Customer {customer_uuid} -> {product_name}")
    pass


def send_confirmation_email(customer_uuid: str, session):
    """Send payment confirmation email to customer."""
    # TODO: Implement your email sending logic
    # Example:
    # - Get customer email from database
    # - Send confirmation email with invoice
    # - Include access instructions
    print(f"[EMAIL] Sending confirmation to customer {customer_uuid}")
    pass


def log_successful_payment(session_uuid: str, amount: float):
    """Log successful payment to database/analytics."""
    # TODO: Implement your logging logic
    # Example:
    # - Store transaction in database
    # - Update analytics
    # - Trigger accounting system
    print(f"[LOG] Successful payment: {session_uuid} - ${amount}")
    pass


def notify_payment_failure(customer_uuid: str, error_message: str):
    """Notify customer about payment failure."""
    # TODO: Implement failure notification
    # Example:
    # - Send email with error details
    # - Suggest alternative payment methods
    # - Provide support contact
    print(f"[NOTIFY FAILURE] Customer {customer_uuid}: {error_message}")
    pass


def log_failed_payment(session_uuid: str, error_message: str):
    """Log failed payment for review."""
    # TODO: Implement failure logging
    print(f"[LOG FAILURE] {session_uuid}: {error_message}")
    pass


def log_cancelled_payment(session_uuid: str):
    """Log cancelled payment."""
    # TODO: Implement cancellation logging
    print(f"[LOG CANCELLED] {session_uuid}")
    pass


# =============================================================================
# Run the application
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting QBitFlow webhook handler...")
    print("📡 Listening on http://localhost:8001")
    print("\nEndpoints:")
    print("  - POST /webhook - Receive webhook events")
    print("  - GET  /success - Handle successful payments")
    print("  - GET  /cancel  - Handle cancelled payments")
    print("\n💡 Make sure to configure these URLs in your QBitFlow dashboard!")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8001)
