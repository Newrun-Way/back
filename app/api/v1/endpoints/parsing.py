from fastapi import APIRouter, UploadFile, File, HTTPException, status
from pathlib import Path
import shutil
import os
from app.core.parser import parse_document # Will create this file

router = APIRouter()

@router.post("/upload-and-parse/")
async def upload_and_parse_hwp(file: UploadFile = File(...)):
    if not file.filename.endswith((".hwp", ".hwpx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .hwp and .hwpx files are allowed"
        )

    # Create a temporary directory to save the uploaded file
    temp_dir = Path("temp_uploads")
    temp_dir.mkdir(exist_ok=True)
    
    file_path = temp_dir / file.filename
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Call the parsing function
        parsed_data = parse_document(str(file_path))
        
        return {"filename": file.filename, "parsed_data": parsed_data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {e}"
        )
    finally:
        # Clean up the temporary file and directory
        if file_path.exists():
            os.remove(file_path)
        if temp_dir.exists() and not os.listdir(temp_dir): # Only remove if empty
            os.rmdir(temp_dir)
