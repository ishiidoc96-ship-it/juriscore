"""
Cloudinary service — handles file uploads, image optimization, and CDN delivery.
"""
import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from typing import Optional, Dict, Any

# Configure Cloudinary from environment or defaults
CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "dilrcexxe")
API_KEY = os.getenv("CLOUDINARY_API_KEY", "486536719931129")
API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "izD5h3kMUnifKE4NxDlYLyi-rwA")

cloudinary.config(
    cloud_name=CLOUD_NAME,
    api_key=API_KEY,
    api_secret=API_SECRET,
    secure=True,
)


def upload_file(
    file_path: str,
    folder: str = "juriscore",
    resource_type: str = "auto",
    public_id: Optional[str] = None,
    tags: Optional[list] = None,
) -> Dict[str, Any]:
    """Upload a file to Cloudinary."""
    params = {
        "folder": folder,
        "resource_type": resource_type,
        "overwrite": True,
    }
    if public_id:
        params["public_id"] = public_id
    if tags:
        params["tags"] = tags

    result = cloudinary.uploader.upload(file_path, **params)
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "format": result.get("format"),
        "width": result.get("width"),
        "height": result.get("height"),
        "bytes": result.get("bytes"),
        "folder": result.get("folder"),
    }


def upload_bytes(
    file_bytes: bytes,
    filename: str,
    folder: str = "juriscore",
    resource_type: str = "auto",
    tags: Optional[list] = None,
) -> Dict[str, Any]:
    """Upload raw bytes to Cloudinary."""
    params = {
        "folder": folder,
        "resource_type": resource_type,
        "overwrite": True,
        "public_id": filename.rsplit(".", 1)[0] if "." in filename else filename,
    }
    if tags:
        params["tags"] = tags

    result = cloudinary.uploader.upload(file_bytes, **params)
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "format": result.get("format"),
        "width": result.get("width"),
        "height": result.get("height"),
        "bytes": result.get("bytes"),
    }


def get_optimized_url(
    public_id: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    quality: str = "auto",
    format: str = "auto",
) -> str:
    """Get an optimized URL for a Cloudinary asset."""
    transforms = {}
    if width:
        transforms["width"] = width
    if height:
        transforms["height"] = height
    transforms["quality"] = quality
    transforms["fetch_format"] = format

    return cloudinary.CloudinaryImage(public_id).build_url(**transforms)


def delete_file(public_id: str) -> bool:
    """Delete a file from Cloudinary."""
    try:
        result = cloudinary.uploader.destroy(public_id)
        return result.get("result") == "ok"
    except Exception:
        return False


def list_files(folder: str = "juriscore", max_results: int = 100) -> list:
    """List files in a Cloudinary folder."""
    try:
        result = cloudinary.api.resources(
            type="upload",
            prefix=folder,
            max_results=max_results,
        )
        return [
            {
                "url": r["secure_url"],
                "public_id": r["public_id"],
                "format": r.get("format"),
                "bytes": r.get("bytes"),
            }
            for r in result.get("resources", [])
        ]
    except Exception:
        return []
