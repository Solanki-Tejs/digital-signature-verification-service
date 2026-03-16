
import os
import shutil
import uuid
import numpy as np
import cv2
import torch
import torch.nn as nn
import torch.nn.functional as F

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
        RETURNING customer_id
    """),{
        "employee_id": data.empID,
        "dob": data.DOB,
        "full_name": data.fullName,
        "email": data.email,
        "embedding": embedding_bytes
    })

    customer_id = result.scalar()

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

    return {
        "status": "success",
        "customer_id": customer_id,
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