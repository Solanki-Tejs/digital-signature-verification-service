from datetime import date
from pydantic import BaseModel

class enrollSchema(BaseModel):
    empID: int
    DOB: date
    fullName: str
    email: str

