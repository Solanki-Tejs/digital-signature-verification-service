import io
import base64
import numpy as np
import cv2
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi import FastAPI, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from utils.database import SessionLocal
from schemas.employee_schema import *
from schemas.customer_schema import *
from services.employee_service import *
from services.customer_service import *
from services.preprocessing_service import *
from dependencies.auth_dependencies import role_required, get_current_user

def numpy_to_base64(img_array: np.ndarray) -> str:
    """Convert numpy image array to base64 PNG string for Swagger display."""
    _, buffer = cv2.imencode(".png", img_array)
    return base64.b64encode(buffer).decode("utf-8")
import sys
sys.path.append("/outputs")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def root():
    return {"message": "Hello world!"}


@app.get("/me")
def get_me(user=Depends(get_current_user)):
    return {"isAuth": True}


@app.post("/login")
def login(data: LoginSchema, response: Response, db: Session = Depends(get_db)):

    token, result = login_service(data, db)

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="Lax",
        secure=False
    )

    return {
        "message": "Login successful",
        "employee_id": result["employee_id"],
        "full_name": result["full_name"],
        "role": result["role"]
    }


@app.post("/update_details")
def update_details(data: UpdateUserSchema, db: Session = Depends(get_db)):

    update_user_service(data, db)

    return {"message": "credentials updated successfully"}


@app.post("/create_employee")
def create_employee(
    data: NewUserSchema,
    user=Depends(role_required(["admin"])),
    db: Session = Depends(get_db)
):

    employee_id = create_employee_service(data, db)

    return {"employee_id": employee_id, "message": "Employee created"}


@app.get("/employee")
def get_employees(db: Session = Depends(get_db)):

    return get_all_employees_service(db)


@app.delete("/delete_employee/{employee_id}")
def delete_employee(employee_id: int, db: Session = Depends(get_db)):

    delete_employee_service(employee_id, db)

    return {"message": "Employee deleted successfully"}



from fastapi import UploadFile, File
from typing import List

from fastapi import Form
@app.post("/enroll_customer")
def enroll_customer(
    empID: int = Form(...),
    DOB: date = Form(...),
    fullName: str = Form(...),
    email: str = Form(...),
    images: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    
    data = enrollSchema(
        empID=empID,
        DOB=DOB,
        fullName=fullName,
        email=email
    )

    return enroll_customer_service(data, images, db)


@app.post("/test_verify")
def test_verify(
    reference_images: List[UploadFile] = File(...),
    test_image: UploadFile = File(...)
):

    return verify_test_service(reference_images, test_image)

@app.post(
    "/test-preprocessing",
    summary="Test Signature Preprocessing",
    description="""
Upload a signature image to see the preprocessing output.
 
**What this does:**
1. Removes ruled/horizontal lines (cheque paper lines)
2. Applies Otsu thresholding to isolate signature strokes
3. Crops tightly to the signature bounding box
4. Resizes to 224×224 for ResNet input
 
**Returns:** An HTML page showing the original and preprocessed images side by side.
    """,
    response_class=HTMLResponse,
    tags=["Preprocessing"]
)
async def test_preprocessing(
    file: UploadFile = File(..., description="Signature image (PNG, JPG, BMP)")
):
    # ── Read uploaded file ────────────────────────────────────
    contents = await file.read()
    nparr    = np.frombuffer(contents, np.uint8)
    original = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
 
    if original is None:
        return HTMLResponse("<h2>Error: Could not read image file.</h2>", status_code=400)
 
    # ── Run preprocessing ─────────────────────────────────────
    tensor, visual = preprocess_signature(original, augment=False)
 
    # ── Convert images to base64 for HTML display ─────────────
    # Resize original to 224x224 for fair comparison
    orig_resized  = cv2.resize(original, (224, 224))
    orig_b64      = numpy_to_base64(orig_resized)
 
    # visual is RGB — convert to BGR for cv2 encoding
    visual_bgr    = cv2.cvtColor(visual, cv2.COLOR_RGB2BGR)
    visual_b64    = numpy_to_base64(visual_bgr)
 
    # ── Tensor stats ──────────────────────────────────────────
    tensor_min  = float(tensor.min())
    tensor_max  = float(tensor.max())
    tensor_mean = float(tensor.mean())
 
    # ── Return HTML response (renders in Swagger UI) ──────────
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Preprocessing Result</title>
        <style>
            body {{
                font-family: 'Segoe UI', sans-serif;
                background: #0f0f0f;
                color: #e0e0e0;
                padding: 30px;
                margin: 0;
            }}
            h1 {{ color: #00d4aa; margin-bottom: 4px; }}
            p.sub {{ color: #888; margin-top: 0; }}
            .grid {{
                display: flex;
                gap: 30px;
                margin-top: 24px;
                flex-wrap: wrap;
            }}
            .card {{
                background: #1a1a1a;
                border: 1px solid #2a2a2a;
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                min-width: 260px;
            }}
            .card h3 {{
                margin: 0 0 12px 0;
                color: #00d4aa;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .card img {{
                width: 224px;
                height: 224px;
                border-radius: 8px;
                border: 1px solid #333;
                image-rendering: pixelated;
            }}
            .badge {{
                display: inline-block;
                background: #00d4aa22;
                color: #00d4aa;
                border: 1px solid #00d4aa44;
                border-radius: 20px;
                padding: 3px 12px;
                font-size: 12px;
                margin-top: 10px;
            }}
            .stats {{
                background: #1a1a1a;
                border: 1px solid #2a2a2a;
                border-radius: 12px;
                padding: 20px;
                margin-top: 24px;
                max-width: 560px;
            }}
            .stats h3 {{
                color: #00d4aa;
                margin: 0 0 14px 0;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .stat-row {{
                display: flex;
                justify-content: space-between;
                padding: 6px 0;
                border-bottom: 1px solid #2a2a2a;
                font-size: 13px;
            }}
            .stat-row:last-child {{ border-bottom: none; }}
            .stat-val {{ color: #00d4aa; font-family: monospace; }}
            .pipeline {{
                background: #1a1a1a;
                border: 1px solid #2a2a2a;
                border-radius: 12px;
                padding: 20px;
                margin-top: 24px;
                max-width: 560px;
            }}
            .pipeline h3 {{
                color: #00d4aa;
                margin: 0 0 14px 0;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .step {{
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 6px 0;
                font-size: 13px;
                color: #aaa;
            }}
            .step-num {{
                background: #00d4aa;
                color: #000;
                border-radius: 50%;
                width: 22px;
                height: 22px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 11px;
                font-weight: bold;
                flex-shrink: 0;
            }}
        </style>
    </head>
    <body>
        <h1>Preprocessing Result</h1>
        <p class="sub">File: <strong>{file.filename}</strong></p>
 
        <div class="grid">
            <div class="card">
                <h3>Original Image</h3>
                <img src="data:image/png;base64,{orig_b64}" alt="Original" />
                <div class="badge">Raw Input</div>
            </div>
            <div class="card">
                <h3>After Preprocessing</h3>
                <img src="data:image/png;base64,{visual_b64}" alt="Preprocessed" />
                <div class="badge">224 × 224 · Clean</div>
            </div>
        </div>
 
        <div class="stats">
            <h3>Tensor Stats (model input)</h3>
            <div class="stat-row">
                <span>Shape</span>
                <span class="stat-val">(3, 224, 224)</span>
            </div>
            <div class="stat-row">
                <span>dtype</span>
                <span class="stat-val">float32</span>
            </div>
            <div class="stat-row">
                <span>Min value</span>
                <span class="stat-val">{tensor_min:.4f}</span>
            </div>
            <div class="stat-row">
                <span>Max value</span>
                <span class="stat-val">{tensor_max:.4f}</span>
            </div>
            <div class="stat-row">
                <span>Mean value</span>
                <span class="stat-val">{tensor_mean:.4f}</span>
            </div>
            <div class="stat-row">
                <span>Normalization</span>
                <span class="stat-val">ImageNet mean/std</span>
            </div>
        </div>
 
        <div class="pipeline">
            <h3>Pipeline Steps Applied</h3>
            <div class="step"><div class="step-num">1</div> Load image</div>
            <div class="step"><div class="step-num">2</div> Convert to grayscale</div>
            <div class="step"><div class="step-num">3</div> Remove ruled/horizontal lines</div>
            <div class="step"><div class="step-num">4</div> Otsu thresholding (background removal)</div>
            <div class="step"><div class="step-num">5</div> Crop to signature bounding box</div>
            <div class="step"><div class="step-num">6</div> Smart resize to 224×224</div>
            <div class="step"><div class="step-num">7</div> Convert grayscale → RGB</div>
            <div class="step"><div class="step-num">8</div> Augmentation skipped (inference mode)</div>
            <div class="step"><div class="step-num">9</div> Normalize (ImageNet stats)</div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.post("/logout")
def logout(response: Response):

    response.delete_cookie(
        key="access_token",
        httponly=True,
        samesite="Lax"
    )

    return {"message": "Logged out successfully"}