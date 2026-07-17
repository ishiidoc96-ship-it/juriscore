"""
Cloudinary upload router — handles file uploads for documents, images, and logos.
"""
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional

logger = logging.getLogger("juriscore")
router = APIRouter()


@router.post("/document")
async def upload_document(
    file: UploadFile = File(...),
    folder: str = Form("juriscore/documents"),
    course: Optional[str] = Form(None),
):
    """Upload a document (PDF, DOCX, PPTX) to Cloudinary."""
    from api.backend.services.cloudinary_service import upload_bytes

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    allowed_types = {
        ".pdf": "raw",
        ".docx": "raw",
        ".doc": "raw",
        ".pptx": "raw",
        ".ppt": "raw",
        ".txt": "raw",
        ".xlsx": "raw",
        ".csv": "raw",
    }

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    resource_type = allowed_types.get(ext, "auto")

    tags = ["document", "law-school"]
    if course:
        tags.append(course.lower().replace(" ", "-"))

    try:
        contents = await file.read()
        result = upload_bytes(
            file_bytes=contents,
            filename=file.filename,
            folder=folder,
            resource_type=resource_type,
            tags=tags,
        )
        return {
            "status": "success",
            "url": result["url"],
            "public_id": result["public_id"],
            "format": result["format"],
            "bytes": result["bytes"],
        }
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    folder: str = Form("juriscore/images"),
):
    """Upload an image (PNG, JPG, SVG) to Cloudinary with optimization."""
    from api.backend.services.cloudinary_service import upload_bytes

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    try:
        contents = await file.read()
        result = upload_bytes(
            file_bytes=contents,
            filename=file.filename,
            folder=folder,
            resource_type="image",
            tags=["image"],
        )
        return {
            "status": "success",
            "url": result["url"],
            "public_id": result["public_id"],
            "format": result["format"],
            "width": result.get("width"),
            "height": result.get("height"),
            "bytes": result["bytes"],
        }
    except Exception as e:
        logger.error(f"Image upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/logo")
async def upload_logo(
    file: UploadFile = File(...),
):
    """Upload the app logo to Cloudinary."""
    from api.backend.services.cloudinary_service import upload_bytes

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    try:
        contents = await file.read()
        result = upload_bytes(
            file_bytes=contents,
            filename="app-logo",
            folder="juriscore/branding",
            resource_type="image",
            tags=["logo", "branding"],
        )
        return {
            "status": "success",
            "url": result["url"],
            "public_id": result["public_id"],
        }
    except Exception as e:
        logger.error(f"Logo upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/files")
async def list_uploaded_files(folder: str = "juriscore"):
    """List files in a Cloudinary folder."""
    from api.backend.services.cloudinary_service import list_files

    files = list_files(folder=folder)
    return {"count": len(files), "files": files}


@router.delete("/{public_id:path}")
async def delete_file(public_id: str):
    """Delete a file from Cloudinary."""
    from api.backend.services.cloudinary_service import delete_file

    success = delete_file(public_id)
    if success:
        return {"status": "deleted", "public_id": public_id}
    raise HTTPException(status_code=404, detail="File not found or delete failed")
