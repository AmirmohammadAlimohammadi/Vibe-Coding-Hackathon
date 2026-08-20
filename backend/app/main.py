from fastapi import FastAPI

app = FastAPI(
    title="Liara Chatbot Backend",
    description="Backend API for the hosting assistant chatbot.",
    version="0.1.0",
)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {"message": "Liara chatbot backend is running."}
