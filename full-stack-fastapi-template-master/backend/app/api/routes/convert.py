from fastapi import APIRouter, File, UploadFile, HTTPException, status
from fastapi.responses import FileResponse
from app.models import TargetFormat
from app.core.config import settings
from app.api.deps import CurrentUser
import os
import tempfile
from pathlib import Path
import redis
import uuid
import json
import filetype
router = APIRouter()

# 连接redis
conn = redis.Redis(host='localhost', port=6379)

@router.post("/{target_format}/")
async def convert_file(current_user: CurrentUser, file: UploadFile = File(...), target_format: TargetFormat = 'pdf'):

    original_filename = file.filename
    if not original_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided for the uploaded file."
        )
    # 创建临时文件存储上传的文档
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(await file.read())
        tmp_file_path = tmp.name

    task_id = str(uuid.uuid4())
    target_fpath = os.path.join(settings.CONVERTED_FILE_STORE_PATH, task_id)
    # 创建目标文件路径，保持原始文件名但更改扩展名为目标格式
    target_filename = str(Path(target_fpath).with_suffix(f".{target_format}").absolute())

    # 确定类型
    source_type = "word"
    kind = filetype.guess(tmp_file_path)
    if kind is not None:
        if kind.extension in ["doc", "docx"]:
            source_type = "word"
        elif kind.extension in [".xls", ".xlsx"]:
            source_type = "excel"
        elif kind.extension in ["ppt", "pptx"]:
            source_type = "powerpoint"
        elif kind.extension in ["pdf"]:
            source_type = "pdfofd"
    else:
        if original_filename.endswith((".doc", ".docx")):
            source_type = "word"
        elif original_filename.endswith((".xls", ".xlsx", ".et")):
            source_type = "excel"
        elif original_filename.endswith(".pdf"):
            source_type = "pdfofd"
        elif original_filename.endswith(".ofd"):
            source_type = "pdfofd"

    # 创建任务
    task = {
        "user": current_user.id,
        "file_path": tmp_file_path,  # 源文件绝对路径
        "target_path": target_filename,  # 转换后文件绝对路径
        "task_key": task_id,  # 任务id, 任务调用方使用此id来轮询结果
        "task_inqueue_time": conn.time()[0],  # 任务入队时间  以 UNIX 时间戳格式表示, redis Time
        "task_inqueue_timeout": 120,  # 任务在队列中的超时时间
        "task_timeout": 60,  # 任务转换超时时间，从任务开始被转换开始计时
        "source_type": source_type,
        "target_type": target_format.lower()
    }
    print(task)

    # 将任务推入队列
    conn.rpush("Convert:" + source_type, json.dumps(task))

    # 等待任务结果
    
    ret_list = conn.blpop("ConvertResult:" + task["task_key"], 180)
    if len(ret_list) == 2:
        print("\r\n")
        print(task["task_key"]+ ": result->:" + str(ret_list[1]))
        conn.delete("ConvertResult:" +task["task_key"])
        print("\r\n")
        print("convert file saved at:"+ task["target_path"])
        print("\r\n")

    try:
        if not os.path.exists(target_filename):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"Failed to convert {tmp_file_path} to {target_format.lower()}.")

        # 读取目标文件内容并作为响应返回
        return FileResponse(target_filename, filename=f"{Path(original_filename).stem}.{target_format}",
                                media_type=f"application/{target_format.lower()}")
    finally:
        # 是否清理？
        # 删除临时文件
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)

