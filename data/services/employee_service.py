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

    token = create_access_token(data={"email": email, "role": result["role"],"employee_id":result["employee_id"],"name":result["full_name"]})
    db.execute(
    text("UPDATE employee SET is_logged_in = TRUE WHERE employee_id = :id"),
    {"id": result["employee_id"]})
    db.commit()
    return token,result,msg

def update_user_service(data, db):
    print(data)

    # 1. Get existing password
    existing = db.execute(
        text("SELECT password_hash FROM employee WHERE employee_id = :id"),
        {"id": data.employeeId}
    ).fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="Employee not found")

    # 2. Decide password
    # if data.password and data.password.strip() != "":
    #     password_hash = create_password_hash(data.password)
    # else:
    #     password_hash = existing[0]  # keep old password

    # 3. Update query
    query = text("""
        UPDATE employee
        SET full_name = :name,
            email = :email,
            role = :role
        WHERE employee_id = :employeeId
        RETURNING employee_id
    """)

    result = db.execute(
        query,
        {
            "name": data.name,
            "email": data.email,
            # "password": password_hash,
            "employeeId": data.employeeId,
            "role": data.role
        }
    ).mappings().first()

    if not result:
        raise HTTPException(status_code=400, detail="Update failed")

    db.commit()


def create_employee_service(data, db):

    query = text("""
        INSERT INTO employee (full_name, email, password_hash, role)
        VALUES (:full_name, :email, :password_hash, :role)
        RETURNING employee_id,full_name
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
    row = result.fetchone() 
    db.commit()

    return dict(row._mapping)


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