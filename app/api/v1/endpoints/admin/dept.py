from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.admin.dept_service import DeptService

router = APIRouter(prefix="/dept", tags=["department"])
service = DeptService()


class DeptCreateRequest(BaseModel):
    dept_name: str


@router.get("/")
def list_dept():
    return service.list()


@router.post("/")
def create_dept(req: DeptCreateRequest):
    dept_id = service.create(req.dept_name)
    return {"dept_id": dept_id, "dept_name": req.dept_name}


@router.put("/{dept_id}")
def update_dept(dept_id: int, req: DeptCreateRequest):
    cnt = service.update(dept_id, req.dept_name)
    if cnt == 0:
        raise HTTPException(404, "Department not found")
    return {"dept_id": dept_id, "dept_name": req.dept_name}


@router.delete("/{dept_id}")
def delete_dept(dept_id: int):
    cnt = service.delete(dept_id)
    if cnt == 0:
        raise HTTPException(404, "Department not found")
    return {"deleted": True}
