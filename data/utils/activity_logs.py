from sqlalchemy import text
from schemas.ActivityLog_schema import *


def log_activity(db, log: ActivityLogCreate):
    db.execute(text("""
        INSERT INTO activity_logs 
        (emp_id, emp_role, action, entity_type, entity_id, description)
        VALUES (:emp_id, :emp_role, :action, :entity_type, :entity_id, :description)
    """), log.dict())

    db.commit()