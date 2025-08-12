import asyncio
import requests
import json
import uuid
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import sys

# API Configuration
@dataclass
class APIConfig:
    base_url: str = "http://localhost:8000"
    timeout: int = 5
    max_retries: int = 3
    retry_delay: float = 0.5

# Test Results Tracking
@dataclass
class TestResult:
    name: str
    passed: bool
    error_message: Optional[str] = None
    response_time: Optional[float] = None

class APIClient:
    """Enhanced API client with better error handling and logging"""
    
    def __init__(self, config: APIConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Metaclip-Test-Suite/1.0'
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request with retry logic and timing"""
        start_time = time.time()
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                url = f"{self.config.base_url}{endpoint}"
                response = self.session.request(
                    method, 
                    url, 
                    timeout=self.config.timeout,
                    **kwargs
                )
                response_time = time.time() - start_time
                return response, response_time
            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay)
                continue
        
        raise last_exception or requests.exceptions.RequestException("Max retries exceeded")
    
    def get(self, endpoint: str, **kwargs) -> Tuple[requests.Response, float]:
        return self._make_request('GET', endpoint, **kwargs)
    
    def post(self, endpoint: str, **kwargs) -> Tuple[requests.Response, float]:
        return self._make_request('POST', endpoint, **kwargs)
    
    def put(self, endpoint: str, **kwargs) -> Tuple[requests.Response, float]:
        return self._make_request('PUT', endpoint, **kwargs)
    
    def delete(self, endpoint: str, **kwargs) -> Tuple[requests.Response, float]:
        return self._make_request('DELETE', endpoint, **kwargs)
    
    def head(self, endpoint: str, **kwargs) -> Tuple[requests.Response, float]:
        return self._make_request('HEAD', endpoint, **kwargs)

class TestSuite:
    """Comprehensive test suite for Metaclip API"""
    
    def __init__(self, config: APIConfig):
        self.config = config
        self.client = APIClient(config)
        self.results: List[TestResult] = []
        self.created_items: List[str] = []  # Track items for cleanup
    
    def _log_test_start(self, test_name: str):
        print(f"\n🧪 Running: {test_name}")
    
    def _log_test_result(self, result: TestResult):
        status = "✅ PASS" if result.passed else "❌ FAIL"
        time_info = f" ({result.response_time:.3f}s)" if result.response_time else ""
        print(f"   {status}{time_info}")
        if result.error_message:
            print(f"   💬 {result.error_message}")
    
    def _add_result(self, name: str, passed: bool, error_message: str = None, response_time: float = None):
        result = TestResult(name, passed, error_message, response_time)
        self.results.append(result)
        self._log_test_result(result)
        return passed
    
    def _cleanup_items(self):
        """Clean up all created items"""
        print("\n🧹 Cleaning up test items...")
        for item_id in self.created_items[:]:  # Copy list to avoid modification during iteration
            try:
                response, _ = self.client.delete(f"/items/{item_id}")
                if response.status_code == 204:
                    self.created_items.remove(item_id)
            except:
                pass  # Ignore cleanup errors
    
    def health_check(self) -> bool:
        """Test server health endpoint"""
        self._log_test_start("Health Check")
        
        try:
            return True
        print(f"✗ Delete item failed: {response.status_code} - {response.text}")
        return False
    except Exception as e:
        print(f"✗ Delete item caused error: {e}")
        return False

def get_file_length() -> bool:
    print("Getting file length...")
    try:
        # First create a file item
        create_response = se.post(f"{base}/items", json={
            "type": "file",
            "content": "test.pdf"
        })
        if create_response.status_code != 201:
            print(f"✗ Failed to create file item: {create_response.status_code}")
            return False
        
        item_id = create_response.text
        
        # Get file length
        response = se.head(f"{base}/file/{item_id}")
        if response.status_code == 410:
            print("✓ Get file length passed (file don't exist, as expected)")
            return True
        print(f"✗ Get file length failed: {response.status_code} - {response.text}")
        return False
    except Exception as e:
        print(f"✗ Get file length caused error: {e}")
        return False

def download_file() -> bool:
    print("Downloading file...")
    try:
        # First create a file item
        create_response = se.post(f"{base}/items", json={
            "type": "file",
            "content": "test.pdf"
        })
        if create_response.status_code != 201:
            print(f"✗ Failed to create file item: {create_response.status_code}")
            return False
        
        item_id = create_response.text
        
        # Try to download file (expecting 410 since file doesn't exist on disk)
        response = se.get(f"{base}/file/{item_id}")
        if response.status_code == 410:
            print("✓ Download file passed (file don't exist, as expected)")
            return True
        print(f"✗ Download file failed: {response.status_code} - {response.text}")
        return False
    except Exception as e:
        print(f"✗ Download file caused error: {e}")
        return False

def upload_file() -> bool:
    print("Uploading file...")
    # First create a file item
    create_response = se.post(f"{base}/items", json={
        "type": "file",
        "content": "test.pdf"
    })
    if create_response.status_code != 201:
        print(f"✗ Failed to create file item: {create_response.status_code}")
        return False
    
    item_id = create_response.text
    if not item_id:
        print("✗ Created file item has no ID")
        return False
    
    # Upload file content
    test_content = b"Test file content"
    files = {'file': ('test.pdf', test_content, 'application/pdf')}
    response = se.put(f"{base}/file/{item_id}", files=files)
    if response.status_code == 201:
        print("✓ Upload file passed")
        return True
    print(f"✗ Upload file failed: {response.status_code} - {response.text}")
    return False

def test_invalid_create_item() -> bool:
    print("Testing invalid item creation...")
    try:
        # Test missing content
        response = se.post(f"{base}/items", json={
            "type": "text"
        })
        if response.status_code != 400:
            print(f"✗ Missing content should return 400, got {response.status_code}")
            return False
        
        # Test invalid type
        response = se.post(f"{base}/items", json={
            "type": "invalid",
            "content": "test"
        })
        if response.status_code != 422:
            print(f"✗ Invalid type should return 422, got {response.status_code}")
            return False
        
        print("✓ Invalid item creation tests passed")
        return True
    except Exception as e:
        print(f"✗ Invalid item creation tests caused error: {e}")
        return False

def test_nonexistent_item() -> bool:
    print("Testing nonexistent item access...")
    try:
        fake_id = str(uuid.uuid4())
        
        # Test get nonexistent item
        response = se.get(f"{base}/items/{fake_id}")
        if response.status_code != 404:
            print(f"✗ Get nonexistent item should return 404, got {response.status_code}")
            return False
        
        # Test delete nonexistent item
        response = se.delete(f"{base}/items/{fake_id}")
        if response.status_code != 404:
            print(f"✗ Delete nonexistent item should return 404, got {response.status_code}")
            return False
        
        print("✓ Nonexistent item access tests passed")
        return True
    except Exception as e:
        print(f"✗ Nonexistent item access tests caused error: {e}")
        return False

## DROP THE DATABASE BEFORE RUNNING TESTS

print("=== Metaclip API Test Suite ===\n")
        
results = [
    health_check(),
    create_text_item(),
    create_file_item(),
    get_all_items(),
    get_specific_item(),
    delete_item(),
    get_file_length(),
    download_file(),
    upload_file(),
    test_invalid_create_item(),
    test_nonexistent_item()
]

print("\n=== Test Suite Completed ===")

if all(results):
    print("🎉 All tests passed!")
else:
    print("❌ Some tests failed")
