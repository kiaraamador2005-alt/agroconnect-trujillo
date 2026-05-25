from fastapi import FastAPI
import os

app = FastAPI(title="AgroBot AI Service")

@app.get("/")
def home():
    return {"message": "AgroBot está en línea"}

@app.get("/health")
def health():
    return {"status": "healthy"}
