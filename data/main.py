from datetime import datetime
import io
import base64
from fastapi.staticfiles import StaticFiles
import numpy as np
import cv2
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi import FastAPI, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from schemas.ActivityLog_schema import ActivityLogCreate
from utils.activity_logs import log_activity
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
app.mount(
    "/uploads",
    StaticFiles(directory="uploads"),  # 🔥 FIX HERE
    name="uploads"
)
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

#CREATE, UPDATE, DELETE, VERIFY,
@app.post("/login")
def login(data: LoginSchema, response: Response, db: Session = Depends(get_db)):

    token, result,msg = login_service(data, db)

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="Lax",
        secure=False
    )

    log_activity(db, ActivityLogCreate(
        emp_id=result["employee_id"],
        emp_role=result["role"],
        action="LOGIN",
        entity_type=result["role"],
        entity_id=result["employee_id"],
        description=f"LOGIN employee {result["full_name"]}"
    ))


    return {
        "message": msg,
        "employee_id": result["employee_id"],
        "full_name": result["full_name"],
        "role": result["role"]
    }


@app.post("/update_details")
def update_details(
    data: UpdateUserSchema,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):

    update_user_service(data, db)

    log_activity(db, ActivityLogCreate(
        emp_id=user["employee_id"],
        emp_role=user["role"],
        action="UPDATE",
        entity_type="EMPLOYEE",
        entity_id=data.employeeId,
        description=f"Updated employee details (ID: {data.employeeId})"
    ))

    return {"message": "credentials updated successfully"}


@app.post("/create_employee")
def create_employee(
    data: NewUserSchema,
    user=Depends(role_required(["admin"])),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    data = create_employee_service(data, db)
    log_activity(db, ActivityLogCreate(
        emp_id=current_user["employee_id"],
        emp_role=current_user["role"],
        action="CREATE",
        entity_type="EMPLOYEE",
        entity_id=data["employee_id"],
        description=f"Employee '{data['full_name']}' created"
    ))
    return {"employee_id": data["full_name"], "message": "Employee created"}


@app.get("/employee")
def get_employees(db: Session = Depends(get_db)):

    return get_all_employees_service(db)


@app.delete("/delete_employee/{employee_id}")
def delete_employee(employee_id: int,current_user = Depends(get_current_user),db: Session = Depends(get_db)):

    delete_employee_service(employee_id, db)
    log_activity(db, ActivityLogCreate(
        emp_id=current_user["employee_id"],
        emp_role=current_user["role"],
        action="DELETE",
        entity_type="EMPLOYEE",
        entity_id=employee_id,
        description=f"Employee 'id num : {employee_id}' has DELETED"
    ))
    return {"message": "Employee deleted successfully"}



from fastapi import UploadFile, File
from typing import List

from fastapi import Form
@app.post("/enroll_customer")
def enroll_customer(
    DOB: date = Form(...),
    fullName: str = Form(...),
    email: str = Form(...),
    images: List[UploadFile] = File(...),
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    employee_email = user["email"]

    query = text("""
        SELECT employee_id
        FROM employee
        WHERE email = :email
    """)

    result = db.execute(query, {"email": employee_email}).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Employee not found")

    empID = user["employee_id"]

    data = enrollSchema(
        empID=empID,
        DOB=DOB,
        fullName=fullName,
        email=email
    )

    data=enroll_customer_service(data, images, db)

    log_activity(db, ActivityLogCreate(
        emp_id=user["employee_id"],
        emp_role=user["role"],
        action="CREATE",
        entity_type="CUSTOMER",
        entity_id=data["customer_id"],  # reference_id in your case
        description=f"Customer '{fullName}' enrolled"
    ))
    return data

@app.post("/verify-signature")
async def verify_signature(
    reference_id: int = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):

    employee_email = user["email"]

    query = text("""
        SELECT employee_id
        FROM employee
        WHERE email = :email
    """)

    result = db.execute(query, {"email": employee_email}).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Employee not found")

    empID = user["employee_id"]

    print(empID)  

    result = verify_customer_signature(reference_id, image, empID, db)
    log_activity(db, ActivityLogCreate(
            emp_id=user["employee_id"],
            emp_role=user["role"],
            action="VERIFY",
            entity_type="SIGNATURE",
            entity_id=reference_id,
            description=(
                f"Signature verified for ref {reference_id} - "
                f"{result['decision']} (score: {result['similarity_score']})"
            )
        ))
    return result

@app.get("/verification-history")
def get_verification_history(
    db: Session = Depends(get_db),
    me = Depends(get_current_user)
):
    role = me["role"]
    email = me["email"]
    print(email)
    emp_query = db.execute(text("""
        SELECT employee_id
        FROM employee
        WHERE email = :email
    """), {
        "email": email
    }).fetchone()

    if not emp_query:
        raise HTTPException(status_code=404, detail="Employee not found")

    employee_id = me["employee_id"]

    if role == "admin":
        result = db.execute(text("""
            SELECT 
                verification_id,
                reference_id,
                employee_id,
                signature_image_path,
                similarity_score,
                final_decision,
                created_at
            FROM customer_signature_verification
            ORDER BY created_at DESC
        """))
    else:
        result = db.execute(text("""
            SELECT 
                verification_id,
                reference_id,
                employee_id,
                signature_image_path,
                similarity_score,
                final_decision,
                created_at
            FROM customer_signature_verification
            WHERE employee_id = :emp_id
            ORDER BY created_at DESC
        """), {
            "emp_id": employee_id
        })

    records = result.fetchall()

    return {
        "role": role,
        "count": len(records),
        "data": [
            {
                "verification_id": row.verification_id,
                "reference_id": row.reference_id,
                "employee_id": row.employee_id,
                "image_path": row.signature_image_path,
                "similarity_score": round(float(row.similarity_score), 4) if row.similarity_score else None,
                "decision": row.final_decision,
                "created_at": str(row.created_at)
            }
            for row in records
        ]
    }


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



@app.get("/logs")
def get_logs(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT * FROM activity_logs ORDER BY created_at DESC"))
    
    logs = [dict(row._mapping) for row in result]

    return logs



@app.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    print(current_user)
    # 1. Remove cookie
    response.delete_cookie(
        key="access_token",
        httponly=True,
        samesite="Lax"
    )

    # 2. Update DB
    db.execute(
        text("UPDATE employee SET is_logged_in = FALSE WHERE employee_id = :id"),
        {"id": current_user["employee_id"]}
    )
    db.commit()

    log_activity(db, ActivityLogCreate(
        emp_id=current_user["employee_id"],
        emp_role=current_user["role"],
        action="LOGOUT",
        entity_type=current_user["role"],
        entity_id=current_user["employee_id"],
        description=f"LOGOUT employee {current_user["name"]}"
    ))

    return {"message": "Logged out successfully"}