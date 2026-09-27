from bootstrap.application import app

broker = app.make("broker")


@broker.task
async def send_welcome_email(email: str, name: str) -> dict:
    """Simulate sending a welcome email asynchronously."""
    print(f"Sending welcome email to {name} <{email}>")
    return {"status": "sent", "email": email, "name": name}


@broker.task
async def process_data(payload: dict) -> dict:
    """Simulate processing a data payload asynchronously."""
    print(f"Processing payload: {payload}")
    result = {k: str(v).upper() for k, v in payload.items()}
    return {"status": "processed", "result": result}
