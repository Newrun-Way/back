from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.admin.project_service import ProjectService

router = APIRouter(prefix="/project", tags=["project"])
service = ProjectService()


class ProjectCreateRequest(BaseModel):
    project_name: str
    dept_id: int


@router.get("/")
def list_project():
    return service.list()


@router.post("/")
def create_project(req: ProjectCreateRequest):
    project_id = service.create(req.project_name, req.dept_id)
    return {"project_id": project_id, "project_name": req.project_name, "dept_id": req.dept_id}


@router.put("/{project_id}")
def update_project(project_id: int, req: ProjectCreateRequest):
    cnt = service.update(project_id, req.project_name, req.dept_id)
    if cnt == 0:
        raise HTTPException(404, "Project not found")
    return {"project_id": project_id, "project_name": req.project_name, "dept_id": req.dept_id}


@router.delete("/{project_id}")
def delete_project(project_id: int):
    cnt = service.delete(project_id)
    if cnt == 0:
        raise HTTPException(404, "Project not found")
    return {"deleted": True}


@router.get("/dept/{dept_id}", response_model=List[ProjectResponse])
def get_projects_by_dept(dept_id: int):
    """
    특정 부서(dept_id)에 속한 프로젝트 목록 조회
    """
    return service.get_by_dept_id(dept_id)
