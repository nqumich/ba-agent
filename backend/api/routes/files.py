"""
文件管理路由

处理文件上传、下载、元数据查询等
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging
import io

from backend.filestore import FileStore, get_file_store
from backend.models.filestore import FileRef, FileCategory
from backend.api.services.excel_processor import create_excel_validator
from backend.api.auth import get_current_user, User

logger = logging.getLogger(__name__)

router = APIRouter()


# ===== 响应模型 =====

class FileUploadResponse(BaseModel):
    """文件上传响应"""
    success: bool = True
    data: Optional[Dict[str, Any]] = None


class FileMetadataResponse(BaseModel):
    """文件元数据响应"""
    success: bool = True
    data: Optional[Dict[str, Any]] = None


class FileListResponse(BaseModel):
    """文件列表响应"""
    success: bool = True
    data: Optional[Dict[str, Any]] = None


# ===== 端点 =====

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """
    上传文件

    - 支持 Excel (.xlsx, .xls)
    - 支持 CSV (.csv)
    - 支持 JSON (.json)
    - 最大文件大小: 50MB
    """
    # 检查文件大小
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大，最大支持 {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    # 检查文件扩展名
    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()

    allowed_extensions = {".xlsx", ".xls", ".csv", ".json"}
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，支持的格式: {', '.join(allowed_extensions)}"
        )

    try:
        # 使用 Excel 验证器验证 Excel 文件
        metadata = {}
        if ext in {".xlsx", ".xls"}:
            validator = create_excel_validator()
            validation_result = validator.validate_upload(filename, content)

            if not validation_result["valid"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"文件验证失败: {', '.join(validation_result['errors'])}"
                )

            metadata = validation_result["metadata"]

            # 添加警告到响应
            if validation_result.get("warnings"):
                logger.warning(f"Excel 文件警告: {validation_result['warnings']}")

        # 获取 FileStore
        file_store = get_file_store()

        # 使用 UploadStore 存储文件
        file_ref = file_store.uploads.store(
            content=content,
            filename=filename,
            session_id=session_id or "default",
            user_id=user_id or "anonymous",
            metadata=metadata  # 存储解析的元数据
        )

        # 构建响应数据
        response_data = {
            "file_id": file_ref.file_id,
            "file_ref": f"upload:{file_ref.file_id}",
            "filename": filename,
            "size": file_ref.size_bytes,
            "category": file_ref.category.value,
            "session_id": file_ref.session_id,
            "created_at": file_ref.metadata.get("created_at"),
            "metadata": metadata
        }

        logger.info(f"文件上传成功: {filename} -> {file_ref.file_id}")

        return FileUploadResponse(data=response_data)

    except Exception as e:
        logger.error(f"文件上传失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"文件上传失败: {str(e)}"
        )


@router.get("/{file_id}/metadata", response_model=FileMetadataResponse)
async def get_file_metadata(
    file_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    获取文件元数据
    """
    try:
        file_store = get_file_store()

        # 创建 FileRef 并获取元数据
        file_ref = FileRef(
            file_id=file_id,
            category=FileCategory.UPLOAD
        )

        # 检查文件是否存在并获取元数据
        metadata = file_store.uploads.get_file_metadata(file_id)

        if not metadata:
            raise HTTPException(status_code=404, detail=f"文件未找到: {file_id}")

        return FileMetadataResponse(data=metadata)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文件元数据失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取文件元数据失败: {str(e)}"
        )


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    下载文件
    """
    try:
        file_store = get_file_store()

        # 创建 FileRef 并读取文件
        file_ref = FileRef(
            file_id=file_id,
            category=FileCategory.UPLOAD
        )

        # 使用 retrieve 方法读取文件内容
        content = file_store.uploads.retrieve(file_ref)

        if content is None:
            raise HTTPException(status_code=404, detail=f"文件未找到: {file_id}")

        # 从元数据获取文件名
        metadata = file_store.uploads.get_file_metadata(file_id)
        filename = metadata.get("filename", file_id) if metadata else file_id

        # 返回文件
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件下载失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"文件下载失败: {str(e)}"
        )


@router.get("", response_model=FileListResponse)
async def list_files(
    category: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
):
    """
    列出文件

    - category: 文件类别过滤
    - session_id: 会话 ID 过滤
    - limit: 最大返回数量
    """
    try:
        file_store = get_file_store()

        # 根据 category 获取对应的 store
        if category:
            try:
                file_category = FileCategory(category)
                store = file_store.get_store(file_category)
                files = store.list_files()
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的类别: {category}")
        else:
            # 列出所有文件（这里简化为只列出上传文件）
            store = file_store.uploads
            # 使用 list_session_files 获取更方便的格式
            upload_files = store.list_session_files(session_id=session_id, limit=limit)

            return FileListResponse(data={
                "total": len(upload_files),
                "files": upload_files
            })

        # 过滤和限制
        if session_id:
            files = [f for f in files if f.session_id == session_id]

        files = files[:limit]

        # 构建响应
        file_list = []
        for f in files:
            # FileMetadata 对象，需要从 file_ref 和 filename 字段获取信息
            file_list.append({
                "file_id": f.file_ref.file_id,
                "filename": f.filename,
                "size": f.file_ref.size_bytes,
                "session_id": f.file_ref.session_id,
                "created_at": f.created_at.isoformat() if f.created_at else None
            })

        return FileListResponse(data={
            "total": len(file_list),
            "files": file_list
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"列出文件失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"列出文件失败: {str(e)}"
        )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    删除文件
    """
    try:
        file_store = get_file_store()

        # 创建 FileRef 并删除文件
        file_ref = FileRef(
            file_id=file_id,
            category=FileCategory.UPLOAD
        )

        success = file_store.uploads.delete(file_ref)

        if not success:
            raise HTTPException(status_code=404, detail=f"文件未找到: {file_id}")

        logger.info(f"文件已删除: {file_id}")

        return {"success": True, "message": "文件已删除"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文件失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"删除文件失败: {str(e)}"
        )


__all__ = ["router"]
