from pathlib import Path
from fastapi_startkit import Application
from fastapi_startkit.fastapi import FastAPIProvider

# Define providers
providers = [FastAPIProvider]

# Initialize Application
app: Application = Application(base_path=str(Path().cwd()), providers=providers)


@app.get("/hello")
async def hello():
    return {"message": "Hello from the Fastapi Starkit!"}


if __name__ == "__main__":
    app.handle_command()
