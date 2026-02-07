"""
文件系统测试配置

提供测试夹具和测试工具
"""

import pytest
import tempfile
from pathlib import Path
from datetime import date

from backend.models.filestore import FileCategory, FileRef
from backend.filestore import FileStore


@pytest.fixture
def temp_dir():
    """临时目录夹具"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def file_store(temp_dir):
    """FileStore 实例夹具"""
    return FileStore(base_dir=temp_dir)


@pytest.fixture
def sample_file_refs():
    """示例文件引用"""
    return [
        FileRef(
            file_id=f'artifact_{i:03d}',
            category=FileCategory.ARTIFACT,
            size_bytes=100 * (i + 1)
        )
        for i in range(5)
    ]


@pytest.fixture
def sample_csv_content():
    """示例 CSV 内容"""
    return b'date,gmv,orders\n2026-01-01,10000,50\n2026-01-02,12000,60'


@pytest.fixture
def sample_json_content():
    """示例 JSON 内容"""
    import json
    return json.dumps({
        'result': 'success',
        'data': [1, 2, 3, 4, 5],
        'metadata': {'version': '1.0'}
    }).encode('utf-8')
