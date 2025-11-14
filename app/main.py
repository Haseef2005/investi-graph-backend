from fastapi import FastAPI

# สร้าง instance ของ FastAPI
app = FastAPI(
    title="Investi-Graph API",
    description="AI Agent for Investment Analysis",
    version="0.1.0"
)

@app.get("/")
def read_root():
    """
    Endpoint แรกของเรา: A simple 'Hello World'
    """
    return {"message": "Welcome to Investi-Graph API!"}

@app.get("/health")
def health_check():
    """
    Endpoint สำคัญสำหรับตรวจสอบว่า API ยังมีชีวิตอยู่
    """
    return {"status": "ok"}