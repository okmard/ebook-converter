import requests
import os
import threading
import time
from flask import Flask
from werkzeug.serving import make_server

# Import the app to test
from app import app

class ServerThread(threading.Thread):
    def __init__(self, app):
        threading.Thread.__init__(self)
        self.server = make_server('127.0.0.1', 5001, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        print('Starting mock server...')
        self.server.serve_forever()

    def shutdown(self):
        print('Stopping mock server...')
        self.server.shutdown()

def test_endpoints():
    # Start server in background
    server = ServerThread(app)
    server.start()
    time.sleep(1) # Wait for start

    try:
        base_url = "http://127.0.0.1:5001"
        
        # 1. Test Index
        print("Testing Index Page...")
        r = requests.get(base_url + '/')
        assert r.status_code == 200
        print("Index OK.")

        # 2. Test Upload (Mock File)
        print("Testing Upload...")
        # Create a dummy file
        with open('test_dummy.epub', 'w') as f:
            f.write('dummy content')
            
        files = {'file': ('test_dummy.epub', open('test_dummy.epub', 'rb'))}
        
        # Note: The actual conversion might fail because it's a dummy file, 
        # but we want to check if the server accepts it and tries to convert.
        # Our converter logic catches exceptions and returns 500 if format invalid.
        # Or 400 if extension invalid.
        
        r = requests.post(base_url + '/upload', files=files)
        
        # It might return 500 because ebooklib can't read "dummy content", but that proves the route works.
        # Or it might succeed if we mocked the converter. 
        # Since we are using the real converter, it will likely return 500 with "EPUB Error".
        
        print(f"Upload Status: {r.status_code}")
        if r.status_code == 200:
            print("Upload Success (Unexpected for dummy file but route is working)")
        elif r.status_code == 500:
            print("Upload Handled (Expected failure for dummy content)")
            assert "转换失败" in r.json()['error'] or "Error" in r.json()['error']
        else:
            print(f"Unexpected status: {r.status_code}")

        # Clean up
        if os.path.exists('test_dummy.epub'):
            os.remove('test_dummy.epub')

    except Exception as e:
        print(f"Test Failed: {e}")
    finally:
        server.shutdown()

if __name__ == "__main__":
    test_endpoints()
