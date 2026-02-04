from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from utils.database import SessionLocal

app = FastAPI()

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
def login(email: str, password: str, db: Session = Depends(get_db)):

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

    if not result or result["password_hash"] != password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {
        "message": "Login successful",
        "employee_id": result["employee_id"],
        "full_name": result["full_name"],
        "role": result["role"]
    }


@app.post("/update_details")
def update_details(
    name: str,
    email: str,
    password: str,
    db: Session = Depends(get_db)
):
    query = text("""
        UPDATE employee
        SET name = :name
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
            "password": password 
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


@app.post("/employee")
def create_employee(
    full_name: str,
    email: str,
    password_hash: str,
    role: str,
    db: Session = Depends(get_db)
):
    query = text("""
        INSERT INTO employee (full_name, email, password_hash, role)
        VALUES (:full_name, :email, :password_hash, :role)
        RETURNING employee_id;
    """)

    try:
        result = db.execute(query, {
            "full_name": full_name,
            "email": email,
            "password_hash": password_hash,
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
