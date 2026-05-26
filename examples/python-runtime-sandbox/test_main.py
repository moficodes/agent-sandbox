# Copyright 2026 The Kubernetes Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import tempfile
from fastapi.testclient import TestClient
import pytest

from main import app

@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        import main
        
        # Monkeypatch /app realpath to use tmpdir
        def mock_get_safe_path(file_path: str) -> str:
            base_dir = tmpdir
            clean_path = file_path.lstrip("/")
            full_path = main.os.path.realpath(main.os.path.join(base_dir, clean_path))
            if main.os.path.commonpath([base_dir, full_path]) != base_dir:
                raise ValueError("Access denied: Path must be within base dir")
            return full_path
        
        original_safe_path_func = getattr(main, "get_safe_path", None)
        main.get_safe_path = mock_get_safe_path
        
        # Also monkeypatch the default write location to use tmpdir
        original_join = main.os.path.join
        def mock_join(a, *p):
            if a == "/app":
                return original_join(tmpdir, *p)
            return original_join(a, *p)
        main.os.path.join = mock_join
        
        try:
            yield TestClient(app)
        finally:
            if original_safe_path_func is not None:
                main.get_safe_path = original_safe_path_func
            main.os.path.join = original_join

def test_upload_default_path(client):
    response = client.post("/upload", files={"file": ("test.txt", b"hello")})
    assert response.status_code == 200
    assert response.json()["message"] == "File 'test.txt' uploaded successfully."

def test_upload_custom_subpath(client):
    response = client.post("/upload", params={"path": "sub/dir/file.txt"}, files={"file": ("file.txt", b"custom content")})
    assert response.status_code == 200
    assert response.json()["message"] == "File 'sub/dir/file.txt' uploaded successfully."

def test_upload_unsafe_path(client):
    response = client.post("/upload", params={"path": "../etc/passwd"}, files={"file": ("file.txt", b"unsafe")})
    assert response.status_code == 403
    assert "Access denied" in response.json()["message"]

def test_upload_unsafe_filename_fallback(client):
    response = client.post("/upload", files={"file": ("../etc/passwd", b"unsafe")})
    assert response.status_code == 403
    assert "Access denied" in response.json()["message"]
