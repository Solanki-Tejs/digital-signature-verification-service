from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from utils.database import SessionLocal
from fastapi.middleware.cors import CORSMiddleware
from utils.hash_password import *
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

class LoginSchema(BaseModel):
    email: str
    password: str

class UpdateUserSchema(BaseModel):
    name: str
    email: str
    password: str

class NewUserSchema(BaseModel):
    full_name: str
    email: str
    password: str
    role: str

@app.get("/")
def root():
    return {"message": "Hello world!"}



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@app.post("/login")
def login(data: LoginSchema, db: Session = Depends(get_db)):
    email = data.email
    password = data.password
    
    print("Login attempt for:", email)
    print("password:", password)

    count_query = text("SELECT COUNT(*) FROM employee")
    user_count = db.execute(count_query).scalar()

    if user_count == 0:
        if email == "admin" and password == "admin":
            create_admin_query = text("""
                INSERT INTO employee (full_name, email, password_hash, role)
                VALUES (:name, :email, :password, :role)
                RETURNING employee_id, full_name, role
            """)
            result = db.execute(
                create_admin_query,
                {
                    "name": "System Admin",
                    "email": "admin",
                    "password": "admin", 
                    "role": "admin"
                }
            ).mappings().first()

            db.commit()

            return {
                "message": "Initial admin created",
                "employee_id": result["employee_id"],
                "full_name": result["full_name"],
                "role": result["role"]
            }

        raise HTTPException(
            status_code=401,
            detail="System not initialized. Use default admin credentials."
        )

    query = text("""
        SELECT employee_id, full_name, email, password_hash, role
        FROM employee
        WHERE email = :email
    """)

    result = db.execute(query, {"email": email}).mappings().first()
    verify=verify_password(password,result["password_hash"])
    if verify == False:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    return {
        "message": "Login successful",
        "employee_id": result["employee_id"],
        "full_name": result["full_name"],
        "role": result["role"]
    }


@app.post("/update_details")
def update_details(
    data:UpdateUserSchema,
    db: Session = Depends(get_db)
):
    name = data.name
    email = data.email
    password = data.password
    query = text("""
        UPDATE employee
        SET full_name = :name
            ,email = :email,
            password_hash = :password
        WHERE email = 'admin'
          AND password_hash = 'admin'
        RETURNING employee_id, role
    """)

    result = db.execute(
        query,
        {   "name": name,
            "email": email,
            "password": create_password_hash(password) 
        }
    ).mappings().first()

    if not result:
        raise HTTPException(
            status_code=400,
            detail="Admin update not allowed or already completed"
        )

    db.commit()

    return {
        "message": "Admin credentials updated successfully",
        "employee_id": result["employee_id"],
        "role": result["role"]
    }


@app.post("/create_employee")
def create_employee(
    data:NewUserSchema,
    db: Session = Depends(get_db)
):
    full_name = data.full_name
    email = data.email
    password = data.password
    role = data.role
    query = text("""
        INSERT INTO employee (full_name, email, password_hash, role)
        VALUES (:full_name, :email, :password_hash, :role)
        RETURNING employee_id;
    """)

    try:
        result = db.execute(query, {
            "full_name": full_name,
            "email": email,
            "password_hash": create_password_hash(password),
            "role": role
        })
        db.commit()
        return {"employee_id": result.scalar(), "message": "Employee created"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# GET all employees
@app.get("/employee")
def get_employees(db: Session = Depends(get_db)):
    query = text("SELECT * FROM employee")
    result = db.execute(query).mappings().all()
    return result
