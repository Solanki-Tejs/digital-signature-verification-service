# Digital Signature Verification Service

<div align="center">

**Backend microservice for automated signature verification using deep learning**

[Features](#features) • [Tech Stack](#tech-stack) • [Architecture](#architecture) • [Setup](#setup) • [API Endpoints](#api-endpoints) • [Future Enhancements](#future-enhancements)

</div>

---

## 📋 Overview

**Glyph** is an AI-powered signature verification system designed to help organizations automate the time-consuming process of manual signature verification. This repository contains the backend service that handles signature enrollment, verification, and user management.

### Problem Statement

Organizations waste significant time manually comparing signatures for authentication purposes. Each verification can take several minutes, and human error rates are considerable.

### Solution

Our system requires only **3-5 sample signatures** during customer enrollment. Once enrolled, any signature can be verified in **seconds** with high accuracy, dramatically reducing verification time and improving reliability.

---

## ✨ Features

### 🔐 User Management
- **Role-Based Access Control**: Admin and User roles with different permissions
- **Admin Capabilities**: Add/delete users, view all verification results
- **User Capabilities**: Enroll customers, verify signatures, view history

### 🖊️ Signature Processing
- **Customer Enrollment**: Register customers with 3-5 signature samples
- **AI-Powered Verification**: Deep learning-based similarity matching
- **Embedding Generation**: Convert signatures to 128-dimensional feature vectors
- **Fast Processing**: Verification results in 2-3 seconds

### 📊 Tracking & Logs
- **Activity Logging**: Complete audit trail of all operations
- **Verification History**: Track all verification attempts with timestamps
- **Email Notifications**: Automated registration confirmations

---

## 🛠️ Tech Stack


| Component | Technology |
|-----------|-----------|
| **Framework** | FastAPI |
| **Deep Learning** | PyTorch |
| **Database** | PostgreSQL |
| **Image Processing** | OpenCV, NumPy |
| **Authentication** | JWT (JSON Web Tokens) |
| **Email Service** | SMTP Integration |
| **Model Architecture** | Siamese CNN |

---

## 🏗️ Architecture

### Project Structure

```
digital-signature-verification-service/
│
├── data/
│   ├── main.py                    # FastAPI application entry point
│   ├── signature_model.pth        # Pre-trained Siamese CNN model
│   │
│   ├── dependencies/
│   │   └── auth_dependencies.py   # JWT authentication middleware
│   │
│   ├── schemas/
│   │   ├── ActivityLog_schema.py  # Activity logging schemas
│   │   ├── customer_schema.py     # Customer data models
│   │   └── employee_schema.py     # Employee/user data models
│   │
│   ├── services/
│   │   ├── customer_service.py    # Customer enrollment & verify signatures
│   │   ├── email_service.py       # Email notification service
│   │   ├── employee_service.py    # User management service
│   │
│   └── utils/
│       ├── activity_logs.py       # Logging utilities
│       ├── config.py               # Configuration management
│       ├── database.py             # PostgreSQL connection
│       ├── hash_password.py        # Password hashing utilities
│       ├── jwt_token.py            # JWT token generation/validation
│       └── pagination.py           # Query pagination helpers
```

### Siamese CNN Model

The core of our verification system uses a **Siamese Convolutional Neural Network** that learns to distinguish between genuine and forged signatures:

```python
class SiameseCNN(nn.Module):
    def __init__(self):
        super().__init__()
        
        self.conv = nn.Sequential(
            nn.Conv2d(1, 32, 3),    # Extract low-level features
            nn.ReLU(),
            nn.MaxPool2d(2),
            
            nn.Conv2d(32, 64, 3),   # Extract high-level features
            nn.ReLU(),
            nn.MaxPool2d(2),
        )
        
        self.fc = nn.Linear(64 * 30 * 30, 128)  # 128-dim embedding
    
    def forward(self, x):
        x = self.conv(x)
        x = x.view(x.size(0), -1)
        x = self.fc(x)
        return F.normalize(x, p=2, dim=1)  # L2 normalized embeddings
```

**How it works:**
1. **Enrollment**: Generate 128-dimensional embeddings for each sample signature
2. **Storage**: Store average embeddings of sample signature in PostgreSQL database
3. **Verification**: Compare new signature embedding with stored embeddings using cosine similarity
4. **Decision**: Return match/no-match based on similarity threshold

---

## 🚀 Setup

### Prerequisites

- Python 3.14
- PostgreSQL 18
- pip (Python package manager)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/Solanki-Tejs/digital-signature-verification-service.git
cd digital-signature-verification-service
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**

Create a `.env` file in the root directory:

```env
# Database Configuration
DB_USER=your_db_username
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=signature_verification

# JWT Configuration
SECRET_KEY=your_super_secret_key_here
ALGORITHM=HS256

# Email Configuration
EMAIL=your_email@gmail.com
APP_PASSWORD=your_email_password
```

4. **Run the server**
```bash
uvicorn data.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### API Documentation

Once running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## 📡 API Endpoints
 
### Authentication & User Management
```http
POST   /login                        # User login (returns JWT token)
GET    /me                           # Get current user details
POST   /logout                       # Logout current session
POST   /change-password              # Change user password
POST   /update_details               # Update user profile information
```
 
### Employee/User Management (Admin)
```http
POST   /create_employee              # Create new employee/user (Admin only)
GET    /employee                     # List all employees (paginated, searchable)
                                     # Query params: search, role, sort, page, limit
DELETE /delete_employee/{employee_id} # Delete employee (Admin only)
GET    /employee-stats               # Get employee statistics
```
 
### Customer Management
```http
POST   /enroll_customer              # Enroll new customer with 3-5 signature samples
                                     # Form data: fullName, email, DOB, images[]
GET    /get_customer                 # List/search customers (paginated)
                                     # Query params: reference_id, email, full_name, 
                                     #               search, employee_id, sort, page, limit
```
 
### Signature Verification
```http
POST   /verify-signature             # Verify signature against enrolled customer
                                     # Form data: reference_id, image
GET    /verification-history         # Get verification history (paginated, filterable)
                                     # Query params: decision, search, sort, page, limit
GET    /recent-verifications         # Get recent verifications (default: 5)
                                     # Query params: limit
```
 
### Dashboard & Analytics
```http
GET    /stats                        # Get dashboard statistics
                                     # Returns: total customers, verifications, success rate, etc.
```
 
### Activity Logs (Admin)
```http
GET    /logs                         # View system activity logs (Admin only)
                                     # Query params: emp_id, action, search, sort, page, limit
```
 
### Utilities
```http
GET    /                             # Health check / root endpoint
POST   /test-preprocessing           # Test signature preprocessing pipeline
                                     # Upload image to see preprocessing output
```

---

## 🔄 Workflow

### Customer Enrollment
```
Upload 3-5 Signatures → Preprocess Images → Generate Embeddings → Store in Database → Send Confirmation Email
```

### Signature Verification
```
Upload Test Signature → Preprocess Image → Generate Embedding → Compare with Stored Embeddings → Return Result (2-3 seconds)
```

---

## 🔮 Future Enhancements

### 1. Advanced Deep Learning Models
- Upgrade to **Triplet Loss** networks for improved accuracy
- Fine-tune on larger, more diverse signature datasets
- Implement **continuous learning** mechanisms for model adaptation

### 2. Real-Time Signature Capture
- Integrate touchscreen/stylus-based input
- Capture **dynamic features**: stroke order, speed, pressure
- Analyze behavioral biometrics for enhanced security

### 3. Multi-Factor Authentication (MFA)
- Combine signature verification with OTP
- Add facial recognition layer
- Integrate employee credential verification

### 4. Scalable Cloud Deployment
- **Dockerization** for containerized deployment
- **Kubernetes** orchestration for high availability
- Deploy on **AWS/Azure/GCP** with load balancing

### 5. Offline Verification Capability
- Enable local verification without internet
- Sync verification results when connection restored
- Support edge computing scenarios


<div align="center">

<h2>Contributors</h2>

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/viren1023">
        <img src="https://github.com/viren1023.png" width="80px;" alt="viren1023"/><br />
        <sub><b>viren1023</b></sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/Solanki-Tejs">
        <img src="https://github.com/Solanki-Tejs.png" width="80px;" alt="Solanki-Tejs"/><br />
        <sub><b>Solanki-Tejs</b></sub>
      </a>
    </td>
  </tr>
</table>

<br/>

<a href="#digital-signature-verification-service">⬆ Back to Top</a>

</div>
