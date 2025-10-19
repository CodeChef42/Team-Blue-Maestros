# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from detection3 import load_model, collect_samples_with_scheme_bias, MODEL_PATH

app = FastAPI(title="Malware URL Detection API", version="1.0")

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Load model ----------
try:
    model, expected_features = load_model(MODEL_PATH)
except Exception as e:
    print(f"❌ Error loading model: {e}")
    model, expected_features = None, None

# ---------- Request model ----------
class URLRequest(BaseModel):
    url: str

# ---------- Routes ----------
@app.get("/")
def root():
    return {"message": "Malware URL Detection API is running"}

@app.post("/scan")
def scan_url(data: URLRequest):
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")

    url = data.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Empty URL")

    try:
        _, verdict = collect_samples_with_scheme_bias(model, expected_features, url)
        return {"url": url, "verdict": verdict}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------- Run ----------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
