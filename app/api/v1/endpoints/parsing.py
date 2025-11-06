from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from pathlib import Path
import shutil, os
from app.core.parser import parse_document

router = APIRouter()

@router.post("/upload-and-parse/")
async def upload_and_parse_hwp(
    file: UploadFile = File(...),
    dept_id: str = Form(None),
    project_id: str = Form(None),
    user_id: str = Form(None)
):
    if not file.filename.endswith((".hwp", ".hwpx")):
        raise HTTPException(status_code=400, detail="Only .hwp/.hwpx allowed")

    # Create a temp directory to save the uploaded file
    temp_dir = Path("temp_uploads")
    temp_dir.mkdir(exist_ok=True)
    file_path = temp_dir / file.filename

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        meta = {k: v for k, v in {"dept_id": dept_id, "project_id": project_id, "user_id": user_id}.items() if v}
        parsed_data = parse_document(str(file_path), doc_id=file.filename, meta=meta)
        
        return {"filename": file.filename, "parsed_data": parsed_data}
    
    except Exception as e:
               raise HTTPException(status_code=500, detail=f"Error processing file: {e}")

    finally:
        if file_path.exists():
            os.remove(file_path)
        if not any(temp_dir.iterdir()):
            temp_dir.rmdir()
