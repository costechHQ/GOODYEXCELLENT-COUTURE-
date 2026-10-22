from fastapi import FastAPI

app = FastAPI(title="GOODYEXCELLENT COUTURE API")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
