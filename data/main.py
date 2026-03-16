from fastapi import FastAPI, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from utils.database import SessionLocal
from schemas.employee_schema import *
from schemas.customer_schema import *
from services.employee_service import *
from services.customer_service import *
from dependencies.auth_dependencies import role_required, get_current_user

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

    token, result,msg = login_service(data, db)

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="Lax",
        secure=False
    )

    return {
        "message": msg,
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

    empID = result[0]

    data = enrollSchema(
        empID=empID,
        DOB=DOB,
        fullName=fullName,
        email=email
    )

    return enroll_customer_service(data, images, db)

@app.post("/verify-signature")
async def verify_signature(
    reference_id: int = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    
    result = verify_customer_signature(reference_id, image, db)

    return result


@app.post("/logout")
def logout(response: Response):

    response.delete_cookie(
        key="access_token",
        httponly=True,
        samesite="Lax"
    )

    return {"message": "Logged out successfully"}