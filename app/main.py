from fastapi import FastAPI

app = FastAPI(title="Trade Store")


@app.get("/health")
def health():
    """Tell the caller the service is up and running."""
    return {"status": "ok"}
