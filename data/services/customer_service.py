
import os
import shutil
import uuid
import numpy as np
import cv2
import torch
import torch.nn as nn
import torch.nn.functional as F
from services.email_service import send_registration_email
import threading
from utils.pagination import paginate_query

from sqlalchemy import text

# -------------------------------
# CONFIG
# -------------------------------

UPLOAD_DIR = "uploads"
TEMP_DIR = "temp_uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

IMG_SIZE = 128
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_PATH = "signature_model.pth"


# -------------------------------
# MODEL
# -------------------------------

class SiameseCNN(nn.Module):

    def __init__(self):
        super().__init__()

        self.conv = nn.Sequential(
            nn.Conv2d(1, 32, 3),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(32, 64, 3),
            nn.ReLU(),
            nn.MaxPool2d(2),
        )

        self.fc = nn.Linear(64 * 30 * 30, 128)

    def forward(self, x):

        x = self.conv(x)

        x = x.view(x.size(0), -1)

        x = self.fc(x)

        return F.normalize(x, p=2, dim=1)


# -------------------------------
# LOAD MODEL
# -------------------------------

model = SiameseCNN().to(DEVICE)

model.load_state_dict(
    torch.load(MODEL_PATH, map_location=DEVICE)
)

model.eval()


# -------------------------------
# IMAGE LOADER
# -------------------------------

def load_image(path):

    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)

    if img is None:
        raise Exception("Invalid image file")

    img = cv2.resize(img, (IMG_SIZE, IMG_SIZE))

    img = torch.from_numpy(img).unsqueeze(0).unsqueeze(0).float() / 255.0

    return img.to(DEVICE)


# -------------------------------
# EMBEDDING GENERATOR
# -------------------------------

def compute_avg_embedding(folder_path):

    embeddings = []

    for file in os.listdir(folder_path):

        if not file.lower().endswith((".png", ".jpg", ".jpeg")):
            continue

        img_path = os.path.join(folder_path, file)

        img_tensor = load_image(img_path)

        with torch.no_grad():
            emb = model(img_tensor)

        embeddings.append(emb.cpu().numpy().flatten())

    if len(embeddings) == 0:
        raise Exception("No valid images found")

    embeddings = np.array(embeddings)

    mean_emb = np.mean(embeddings, axis=0)

    mean_emb = mean_emb / np.linalg.norm(mean_emb)

    return mean_emb


# -------------------------------
# ENROLL CUSTOMER SERVICE
# -------------------------------

def enroll_customer_service(data, images, db):

    if len(images) < 3:
        raise Exception("Minimum 3 signature images required")

    # -------------------------------
    # CREATE TEMP FOLDER
    # -------------------------------

    temp_id = str(uuid.uuid4())

    temp_folder = os.path.join(TEMP_DIR, temp_id)

    os.makedirs(temp_folder, exist_ok=True)

    # -------------------------------
    # SAVE UPLOADED IMAGES
    # -------------------------------

    for img in images:

        if not img.content_type.startswith("image"):
            raise Exception("Invalid file type")

        file_path = os.path.join(temp_folder, img.filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(img.file, buffer)

    # -------------------------------
    # COMPUTE EMBEDDING
    # -------------------------------

    avg_embedding = compute_avg_embedding(temp_folder)

    embedding_bytes = avg_embedding.astype("float32").tobytes()

    # -------------------------------
    # INSERT INTO DATABASE
    # -------------------------------

    result = db.execute(text("""
        INSERT INTO customer_signature (
            employee_id,
            dob,
            full_name,
            email,
            avg_embedding
        )
        VALUES (
            :employee_id,
            :dob,
            :full_name,
            :email,
            :embedding
        )
        RETURNING customer_id, reference_id,full_name
    """), {
        "employee_id": data.empID,
        "dob": data.DOB,
        "full_name": data.fullName,
        "email": data.email,
        "embedding": embedding_bytes
    })

    row = result.fetchone()

    customer_id = row.customer_id
    reference_id = row.reference_id
    
    # -------------------------------
    # MOVE IMAGES TO FINAL FOLDER
    # -------------------------------

    final_folder = os.path.join(UPLOAD_DIR, f"customer_{customer_id}")

    shutil.move(temp_folder, final_folder)

    # -------------------------------
    # UPDATE SIGNATURE PATH
    # -------------------------------

    db.execute(text("""
        UPDATE customer_signature
        SET initial_signature_path = :path
        WHERE customer_id = :cid
    """),{
        "path": final_folder,
        "cid": customer_id
    })

    db.commit()

    # -------------------------------
    # SEND EMAIL (ASYNC)
    # -------------------------------

    threading.Thread(
        target=send_registration_email,
        args=(data.email, data.fullName, reference_id)
    ).start()

    return {
        "status": "success",
        "customer_id": reference_id,
        "signature_folder": final_folder
    }



# CREATE SEQUENCE customer_id_seq START 1;
# CREATE SEQUENCE reference_seq START 1000000000;

# CREATE TABLE customer_signature (
#     customer_id BIGINT PRIMARY KEY DEFAULT nextval('customer_id_seq'),
#     reference_id BIGINT UNIQUE DEFAULT nextval('reference_seq'),
#     employee_id INTEGER NOT NULL,
#     dob DATE,
#     full_name VARCHAR(255) NOT NULL,
#     email VARCHAR(255),
#     avg_embedding BYTEA,
#     initial_signature_path VARCHAR(500),
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );



from fastapi import HTTPException
from sklearn.metrics.pairwise import cosine_similarity


THRESHOLD = 0.95   # adjust later after testing


# def verify_customer_signature(reference_id, image, db):

#     # -------------------------------
#     # GET EMBEDDING FROM DATABASE
#     # -------------------------------

#     result = db.execute(text("""
#         SELECT avg_embedding
#         FROM customer_signature
#         WHERE reference_id = :rid
#     """), {
#         "rid": reference_id
#     }).fetchone()

#     if not result:
#         raise HTTPException(status_code=404, detail="Customer not found")

#     reference_embedding = np.frombuffer(result.avg_embedding, dtype="float32")

#     # -------------------------------
#     # SAVE TEMP IMAGE
#     # -------------------------------

#     temp_id = str(uuid.uuid4())
#     temp_path = os.path.join(TEMP_DIR, f"{temp_id}.png")

#     with open(temp_path, "wb") as buffer:
#         shutil.copyfileobj(image.file, buffer)

#     # -------------------------------
#     # COMPUTE TEST EMBEDDING
#     # -------------------------------

#     img_tensor = load_image(temp_path)

#     with torch.no_grad():
#         test_embedding = model(img_tensor)

#     test_embedding = test_embedding.cpu().numpy().flatten()

#     # -------------------------------
#     # COSINE SIMILARITY
#     # -------------------------------

#     score = cosine_similarity(
#         reference_embedding.reshape(1, -1),
#         test_embedding.reshape(1, -1)
#     ).item()

#     os.remove(temp_path)

#     return {
#         "reference_id": reference_id,
#         "match": bool(score > THRESHOLD),
#         "similarity_score": round(float(score), 4)
#     }



import os

def get_first_image(folder_path):
    files = os.listdir(folder_path)

    # filter only image files (optional but recommended)
    image_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

    if not image_files:
        return None

    # get first image
    first_image = image_files[0]

    # full path
    full_path = os.path.join(folder_path, first_image)

    return full_path



def verify_customer_signature(reference_id, image,empID, db):
    print(empID)
    # -------------------------------
    # GET EMBEDDING + EMPLOYEE ID
    # -------------------------------

    result = db.execute(text("""
        SELECT avg_embedding, initial_signature_path
        FROM customer_signature
        WHERE reference_id = :rid
    """), {
        "rid": reference_id
    }).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Customer not found")

    reference_embedding = np.frombuffer(result.avg_embedding, dtype="float32")
    employee_id = empID

    # -------------------------------
    # SAVE TEMP IMAGE
    # -------------------------------

    temp_id = str(uuid.uuid4())
    temp_path = os.path.join(TEMP_DIR, f"{temp_id}.png")

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    # -------------------------------
    # COMPUTE TEST EMBEDDING
    # -------------------------------

    img_tensor = load_image(temp_path)

    with torch.no_grad():
        test_embedding = model(img_tensor)

    test_embedding = test_embedding.cpu().numpy().flatten()

    # -------------------------------
    # COSINE SIMILARITY
    # -------------------------------

    score = cosine_similarity(
        reference_embedding.reshape(1, -1),
        test_embedding.reshape(1, -1)
    ).item()

    # -------------------------------
    # DECISION LOGIC
    # -------------------------------

    if score >= 0.95:
        decision = "VALID"
    elif score >= 0.90:
        decision = "SUSPICIOUS"
    else:
        decision = "MISMATCH"

    # -------------------------------
    # SAVE IMAGE (OPTIONAL BUT RECOMMENDED)
    # -------------------------------

    verify_folder = os.path.join(UPLOAD_DIR, "verifications")
    os.makedirs(verify_folder, exist_ok=True)

    final_image_path = os.path.join(verify_folder, f"{temp_id}.png")
    shutil.move(temp_path, final_image_path)

    # -------------------------------
    # INSERT INTO VERIFICATION TABLE
    # -------------------------------

    db.execute(text("""
        INSERT INTO customer_signature_verification (
            reference_id,
            employee_id,
            signature_image_path,
            similarity_score,
            final_decision
        )
        VALUES (
            :reference_id,
            :employee_id,
            :path,
            :score,
            :decision
        )
    """), {
        "reference_id": reference_id,
        "employee_id": employee_id,
        "path": final_image_path,
        "score": float(score),
        "decision": decision
    })

    db.commit()
    folder = result.initial_signature_path
    return {
        "reference_id": reference_id,
        "match": decision == "VALID",
        "decision": decision,
        "similarity_score": round(float(score), 4),
        "uploaded_image": final_image_path,
        "reference_image": get_first_image(folder)
    }




def get_all_customers_service(db, page, limit, search=None, employee_id=None, sort="desc"):

    select_query = """
        SELECT 
            customer_id,
            reference_id,
            employee_id,
            full_name,
            email,
            dob,
            initial_signature_path,
            created_at
    """

    base_query = """
        FROM customer_signature
    """

    conditions = []
    params = {}

    # 🔍 Search (name, email, reference_id)
    if search:
        conditions.append("""
            (
                full_name ILIKE :search OR
                email ILIKE :search OR
                CAST(reference_id AS TEXT) ILIKE :search
            )
        """)
        params["search"] = f"%{search}%"

    # 👨‍💼 Filter by employee_id
    if employee_id:
        conditions.append("employee_id = :employee_id")
        params["employee_id"] = employee_id

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # 🔽 Sorting (safe handling)
    sort = sort.lower()
    if sort not in ["asc", "desc"]:
        sort = "desc"

    order = "ASC" if sort == "asc" else "DESC"
    order_by = f"ORDER BY created_at {order}"

    return paginate_query(
        db=db,
        select_query=select_query,
        base_query=base_query,
        where_clause=where_clause,
        params=params,
        page=page,
        limit=limit,
        order_by=order_by
    )

# CREATE SEQUENCE verification_id_seq START 1;

# CREATE TABLE customer_signature_verification (
#     verification_id BIGINT PRIMARY KEY DEFAULT nextval('verification_id_seq'),

#     reference_id BIGINT NOT NULL,
#     employee_id INTEGER NOT NULL,

#     signature_image_path VARCHAR(500),

#     similarity_score DOUBLE PRECISION,

#     final_decision VARCHAR(20) CHECK (
#         final_decision IN ('VALID', 'SUSPICIOUS', 'MISMATCH')
#     ),

#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );