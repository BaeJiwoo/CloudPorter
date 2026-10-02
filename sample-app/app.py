from fastapi import FastAPI

from pydantic import BaseModel

class EchoRequest(BaseModel):
    message: str

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello Deploy"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/echo")
def echo(request: EchoRequest):
    return {
        "received": request.message
    }