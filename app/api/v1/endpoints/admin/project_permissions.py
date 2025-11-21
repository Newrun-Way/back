from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.admin.project_permission_service import ProjectPermissionService

router = APIRouter(prefix="/project", tags=["admin-project"])
service = ProjectPermissionService()


class PermissionUpdateRequest(BaseModel):
    dept_ids: list[int]


@router.put("/{project_id}/permissions")
def update_project_permissions(project_id: int, req: PermissionUpdateRequest):

    owner_dept = service.get_owner_dept(project_id)
    if owner_dept is None:
        raise HTTPException(404, "Project not found")

    # owner dept 는 협업 목록에서 자동 제외되도록 강제
    if owner_dept in req.dept_ids:
        req.dept_ids.remove(owner_dept)

    service.update_permissions(project_id, req.dept_ids)

    return {
        "project_id": project_id,
        "owner_dept": owner_dept,
        "collabo_depts": req.dept_ids
    }


@router.get("/{project_id}/permissions")
def get_project_permissions(project_id: int):
    owner_dept = service.get_owner_dept(project_id)
    if owner_dept is None:
        raise HTTPException(404, "Project not found")

    collabo = service.list_permissions(project_id)
    return {
        "project_id": project_id,
        "owner_dept": owner_dept,
        "collabo_depts": collabo
    }
