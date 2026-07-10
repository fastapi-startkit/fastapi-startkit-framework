from fastapi_startkit.storage import Storage


async def stream(path: str):
    """Stream a file from S3 back to the client."""
    return Storage.disk("s3").stream(path)
