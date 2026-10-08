"""Start both local servers: python run.py"""
import os
import subprocess
import sys
import time
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)
from dotenv import load_dotenv
load_dotenv()

if __name__ == '__main__':
    import httpx
    from werkzeug.serving import run_simple
    from frontend.app import app
    backend = subprocess.Popen([sys.executable,'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000'])
    try:
        for _ in range(50):
            if backend.poll() is not None:
                raise RuntimeError('Backend stopped. Check whether port 8000 is in use.')
            try:
                if httpx.get('http://127.0.0.1:8000/health',timeout=1,trust_env=False).status_code==200:
                    break
            except httpx.HTTPError:
                time.sleep(.2)
        else:
            raise RuntimeError('Backend did not start')
        print('\nFinPath website: http://127.0.0.1:5000\nAPI docs: http://127.0.0.1:8000/docs\nPress Ctrl+C to stop.\n')
        run_simple('127.0.0.1',5000,app,use_reloader=False,use_debugger=False,threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        backend.terminate()
        try:
            backend.wait(timeout=10)
        except subprocess.TimeoutExpired:
            backend.kill()
