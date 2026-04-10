from pydantic import BaseModel

class LoginSchema(BaseModel):
    email: str
    password: str


class UpdateUserSchema(BaseModel):
    name: str
    email: str
    # password: str
    employeeId: int
    role: str


class NewUserSchema(BaseModel):
    full_name: str
    email: str
    password: str
    role: str