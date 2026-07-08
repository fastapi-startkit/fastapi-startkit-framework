from fastapi_startkit import Application
from fastapi_startkit.fastapi import FastAPIProvider

app: Application = Application(providers=[FastAPIProvider])


@app.get("/")
async def index():
    return {"message": "Hello, World!"}
