from urllib import response

from sqlalchemy import text
from fastapi import HTTPException
from utils.hash_password import create_password_hash, verify_password
from utils.jwt_token import create_access_token


def login_service(data, db):

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
                    "password": create_password_hash("admin"),
                    "role": "admin"
                }
            ).mappings().first()

            db.commit()

            token = create_access_token(data={"email": email, "role": result["role"]})
            msg="Initial admin created"
            return token,result,msg

        raise HTTPException(
            status_code=401,
            detail="System not initialized. Use default admin credentials."
        )

    query = text("""
        SELECT employee_id, full_name, email, password_hash, role
        FROM employee
        WHERE email = :email
    """)
    msg="Login successful"
    result = db.execute(query, {"email": email}).mappings().first()
    verify=verify_password(password,result["password_hash"])
    if verify == False:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    token = create_access_token(data={"email": email, "role": result["role"]})
    
    return token,result,msg


def update_user_service(data, db):

    query = text("""
        UPDATE employee
        SET full_name = :name,
            email = :email,
            password_hash = :password
        WHERE employee_id = :employeeId
        RETURNING employee_id
    """)

    result = db.execute(
        query,
        {
            "name": data.name,
            "email": data.email,
            "password": create_password_hash(data.password),
            "employeeId": data.employeeId
        }
    ).mappings().first()

    if not result:
        raise HTTPException(status_code=400, detail="Update failed")

    db.commit()


def create_employee_service(data, db):

    query = text("""
        INSERT INTO employee (full_name, email, password_hash, role)
        VALUES (:full_name, :email, :password_hash, :role)
        RETURNING employee_id
    """)

    result = db.execute(
        query,
        {
            "full_name": data.full_name,
            "email": data.email,
            "password_hash": create_password_hash(data.password),
            "role": data.role
        }
    )

    db.commit()

    return result.scalar()


def get_all_employees_service(db):

    query = text("SELECT * FROM employee")

    return db.execute(query).mappings().all()


def delete_employee_service(employee_id, db):

    query = text("""
        DELETE FROM employee
        WHERE employee_id = :employee_id
        RETURNING employee_id
    """)

    result = db.execute(
        query,
        {"employee_id": employee_id}
    ).mappings().first()

    if not result:
        raise HTTPException(status_code=404, detail="Employee not found")

    db.commit()