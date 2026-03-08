import asyncio
import uuid
import pytest
from database.models import BookingStatus
from services.booking_manager import create_booking, get_booking

pytestmark = pytest.mark.asyncio

@pytest.fixture
def clean_in_memory_bookings():
    # Clear in-memory before test
    import services.booking_manager as bm
    bm._in_memory_bookings.clear()
    yield

async def test_payment_gateway_mock(clean_in_memory_bookings):
    """Test that creating a booking generates a payment URL and triggers webhook simulaton."""
    offer = {
        "price": 500000,
        "origin": "Jakarta",
        "destination": "Surabaya",
        "train_name": "Argo Bromo",
        "departure_time": "08:00",
        "arrival_time": "16:00"
    }
    
    # Mute actual DB functions on booking_manager
    import services.booking_manager
    import services.payment_gateway
    original_persist = services.booking_manager._persist_to_db
    original_get_db = services.booking_manager._get_from_db
    original_gateway = services.payment_gateway.create_payment_link
    
    async def noop_persist(order):
        raise Exception("Mock DB Failure")
        
    async def noop_get_db(bid):
        raise Exception("Mock DB Failure")
        
    async def mock_gateway(bid, amount, method):
        return f"https://pay.openclaw.local/checkout/{bid}/MOCK"
        
    services.booking_manager._persist_to_db = noop_persist
    services.booking_manager._get_from_db = noop_get_db
    services.payment_gateway.create_payment_link = mock_gateway
    
    # 1. Create booking (should trigger gateway mock)
    order = await create_booking(
        user_id="user_123",
        travel_type="train",
        offer=offer,
        passenger_name="Budi",
        payment_method="BCA"
    )
    
    assert order["status"] == "pending_payment"
    assert "payment_url" in order
    assert order["payment_url"].startswith("https://pay.openclaw.local/checkout/")
    
    booking_id = order["booking_id"]
    
    # 2. To test the async webhook we manually call the webhook endpoint function
    from api.payment_hook import payment_webhook, MidtransWebhookPayload
    
    # Mock the SHA512 signature
    import hashlib
    import os
    server_key = "test_key"
    os.environ["MIDTRANS_SERVER_KEY"] = server_key
    order_id = booking_id
    status_code = "200"
    gross_amount = "500000.00"
    payload_str = f"{order_id}{status_code}{gross_amount}{server_key}"
    sig = hashlib.sha512(payload_str.encode('utf-8')).hexdigest()
    
    payload = MidtransWebhookPayload(
        transaction_time="2023-01-01 10:00:00",
        transaction_status="settlement",
        transaction_id="TRX-1234",
        status_message="Success, transaction is found",
        status_code=status_code,
        signature_key=sig,
        payment_type="bank_transfer",
        order_id=order_id,
        merchant_id="M123",
        gross_amount=gross_amount,
        fraud_status="accept",
        currency="IDR"
    )
    
    assert payload.transaction_id == "TRX-1234"
    
    # Mute actual DB functions on booking_manager
    import services.booking_manager
    original_persist = services.booking_manager._persist_to_db
    original_get_db = services.booking_manager._get_from_db
    
    async def noop_persist(order):
        raise Exception("Mock DB Failure")
        
    async def noop_get_db(bid):
        raise Exception("Mock DB Failure")
        
    services.booking_manager._persist_to_db = noop_persist
    services.booking_manager._get_from_db = noop_get_db
    
    # Needs a mock request to pass to the FastAPI route
    class MockRequest:
        pass
        
    # We must patch issue_ticket so it doesn't run in the background causing race conditions
    import api.payment_hook
    original_issue = api.payment_hook.issue_ticket
    
    issued_pnr = None
    
    async def mock_issue(bid):
        nonlocal issued_pnr
        import uuid
        pnr = str(uuid.uuid4())[:6].upper()
        issued_pnr = pnr
        # Simply update memory directly
        order = await get_booking(bid)
        if order:
            order["status"] = "issued"
            order["ticket_code"] = pnr

    api.payment_hook.issue_ticket = mock_issue
    class MockBackgroundTasks:
        def add_task(self, func, *args, **kwargs):
            import asyncio
            asyncio.create_task(func(*args, **kwargs))

    res = await payment_webhook(payload, MockRequest(), MockBackgroundTasks())
    assert res["status"] == "ok"
    
    api.payment_hook.issue_ticket = original_issue
    services.booking_manager._persist_to_db = original_persist
    services.booking_manager._get_from_db = original_get_db
    services.payment_gateway.create_payment_link = original_gateway
    
    # Wait briefly for background tasks
    await asyncio.sleep(0.1)
    
    # 3. Check memory to see if status updated
    updated_order = await get_booking(booking_id)
    assert updated_order["status"] == "issued"  # Since our mock updated it to issued instantly
    assert "ticket_code" in updated_order
    assert len(updated_order["ticket_code"]) == 6
