import requests
import time

# Test scanning a directory that already has indexed files
url = "http://localhost:8000/api/scan"
data = {
    "path": r"D:\DOCS\Music\01. Compositions\19.01",
    "resume": False
}

print("Starting scan test...")
response = requests.post(url, json=data)
print(f"Scan initiated: {response.json()}")

# Poll for status
time.sleep(2)
status_url = "http://localhost:8000/api/scan/status"
response = requests.get(status_url)
status = response.json()

print("\n=== Scan Results ===")
if status.get('result'):
    result = status['result']
    print(f"New files indexed: {result.get('files_added', 0)}")
    print(f"Files skipped (already indexed): {result.get('files_skipped', 0)}")
    print(f"Errors: {result.get('errors', 0)}")
    print(f"Time taken: {result.get('elapsed_time', 0):.2f} seconds")
    print(f"Files per second: {result.get('files_per_second', 0):.2f}")
else:
    print("Scan still in progress or no results yet")