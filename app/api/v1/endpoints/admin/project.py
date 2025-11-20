from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.project_service import ProjectService

router = APIRouter(prefix="/project", tags=["project"])
service = ProjectService()


class ProjectCreateRequest(BaseModel):
    project_name: str


@router.get("/")
def list_project():
    return service.list()


@router.post("/")
def create_project(req: ProjectCreateRequest):
    project_id = service.create(req.project_name)
    return {"project_id": project_id, "project_name": req.project_name}


@router.put("/{project_id}")
def update_project(project_id: int, req: ProjectCreateRequest):
    cnt = service.update(project_id, req.project_name)
    if cnt == 0:
        raise HTTPException(404, "Project not found")
    return {"project_id": project_id, "project_name": req.project_name}


@router.delete("/{project_id}")
def delete_project(project_id: int):
    cnt = service.delete(project_id)
    if cnt == 0:
        raise HTTPException(404, "Project not found")
    return {"deleted": True}
