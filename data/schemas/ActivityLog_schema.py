from pydantic import BaseModel
from typing import Optional

class ActivityLogCreate(BaseModel):
    emp_id: int
    emp_role: str
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    description: Optional[str] = None