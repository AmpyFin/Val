from fastapi import FastAPI

app = FastAPI(title="Val Strategy Service (skeleton)")

@app.get("/health")
def health():
    return {"status": "ok", "service": "strategy", "version": "0.0.1"}
