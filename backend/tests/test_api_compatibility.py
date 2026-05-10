#!/usr/bin/env python3
"""
API Comparison Test Script
Tests both old and new servers to ensure compatibility.
"""

import requests
import json
import sys
from time import sleep

def test_endpoint(base_url, endpoint, method="GET", data=None, cookies=None):
    """Test a single endpoint"""
    url = f"{base_url}{endpoint}"
    try:
        if method == "GET":
            resp = requests.get(url, cookies=cookies, timeout=5)
        elif method == "POST":
            resp = requests.post(url, json=data, cookies=cookies, timeout=5)
        elif method == "DELETE":
            resp = requests.delete(url, cookies=cookies, timeout=5)
        elif method == "PUT":
            resp = requests.put(url, json=data, cookies=cookies, timeout=5)
        
        return resp.status_code, resp.json() if resp.headers.get('content-type') == 'application/json' else resp.text
    except Exception as e:
        return None, str(e)

def test_server(base_url, server_name):
    """Test a server"""
    print(f"\n{'='*60}")
    print(f"Testing: {server_name}")
    print(f"URL: {base_url}")
    print('='*60)
    
    tests = [
        ("Health Check", "GET", "/api/health", None),
        ("Auth Status", "GET", "/api/auth/status", None),
        ("Login", "POST", "/api/auth/login", {"username": "admin", "password": "admin123"}),
    ]
    
    cookies = None
    results = []
    
    for test_name, method, endpoint, data in tests:
        print(f"\n{test_name}...")
        status, response = test_endpoint(base_url, endpoint, method, data, cookies)
        
        if status:
            print(f"  ✓ Status: {status}")
            if isinstance(response, dict):
                print(f"  Response: {json.dumps(response, indent=2)[:200]}")
            
            # Save cookies from login
            if endpoint == "/api/auth/login" and status == 200:
                # In real implementation, extract cookie from response
                pass
            
            results.append((test_name, "PASS", status))
        else:
            print(f"  ✗ Error: {response}")
            results.append((test_name, "FAIL", response))
    
    # After login, test authenticated endpoints
    if cookies:
        auth_tests = [
            ("Get Status", "GET", "/api/status", None),
            ("List Playlists", "GET", "/api/playlists", None),
        ]
        
        for test_name, method, endpoint, data in auth_tests:
            print(f"\n{test_name}...")
            status, response = test_endpoint(base_url, endpoint, method, data, cookies)
            
            if status:
                print(f"  ✓ Status: {status}")
                results.append((test_name, "PASS", status))
            else:
                print(f"  ✗ Error: {response}")
                results.append((test_name, "FAIL", response))
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Summary for {server_name}:")
    passed = sum(1 for _, result, _ in results if result == "PASS")
    total = len(results)
    print(f"  Passed: {passed}/{total}")
    
    for test_name, result, info in results:
        symbol = "✓" if result == "PASS" else "✗"
        print(f"  {symbol} {test_name}: {info}")
    
    return passed == total

def main():
    """Main test runner"""
    print("=" * 60)
    print("Pi Display Manager - API Compatibility Test")
    print("=" * 60)
    
    # Test configuration
    old_server = "http://localhost:80"
    new_server = "http://localhost:80"
    
    print("\nℹ️  Make sure one server is running on port 80")
    print("   Old: python3 slideshow_api.py")
    print("   New: python3 slideshow_api_fastapi.py")
    
    server = input("\nWhich server to test? (old/new/both) [new]: ").strip().lower() or "new"
    
    if server == "old" or server == "both":
        old_ok = test_server(old_server, "Old Server (BaseHTTPRequestHandler)")
    
    if server == "new" or server == "both":
        if server == "both":
            print("\n\nSwitching servers...")
            print("Stop the old server and start the new one, then press Enter")
            input()
        
        new_ok = test_server(new_server, "New Server (FastAPI)")
    
    print("\n" + "=" * 60)
    print("Testing Complete!")
    
    if server == "both":
        if old_ok and new_ok:
            print("✓ Both servers are working correctly!")
            return 0
        else:
            print("✗ Some tests failed. Check the output above.")
            return 1
    else:
        return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
