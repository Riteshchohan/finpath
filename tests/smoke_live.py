"""Optional end-to-end HTTP check. Uses temporary synthetic data and ports 5000/8000.
Run from project root: python tests/smoke_live.py
"""
import os
import re
import sys
import time
import json
import tempfile
import subprocess
from pathlib import Path
from datetime import date,timedelta
import httpx

ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as directory:
    env=dict(os.environ,FINPATH_DATA=directory,ENABLE_HF='0',CHAT_PROVIDER='local')
    log=open(Path(directory)/'server.log','w+')
    proc=subprocess.Popen([sys.executable,'run.py'],cwd=ROOT,env=env,stdout=log,stderr=log)
    try:
        with httpx.Client(base_url='http://127.0.0.1:5000',trust_env=False,timeout=30) as c:
            for _ in range(100):
                if proc.poll() is not None:
                    raise RuntimeError('Server startup failed')
                try:
                    r=c.get('/')
                    if r.status_code==200:break
                except httpx.HTTPError:
                    time.sleep(.1)
            else:raise RuntimeError('Startup timed out')
            csrf=re.search(r'name="csrf-token" content="([^"]+)"',r.text).group(1)
            h={'X-CSRF-Token':csrf}
            creds={'email':'flow-check@example.com','password':'flow-check-password-123'}
            assert c.post('/api/auth/register',json=creds,headers=h).status_code==201
            r=c.post('/api/auth/login',json=creds,headers=h)
            assert r.status_code==200,r.text
            assert 'token' not in r.json() and c.get('/session').json()['signed_in']
            content=(ROOT/'samples/sample.csv').read_bytes()
            # The bundled fixture covers these dates; regenerate and adjust if replacing it.
            r=c.post('/api/statements',headers=h,files={'file':('sample.csv',content,'text/csv')},data={'start_date':'2026-04-01','end_date':'2026-09-30'})
            assert r.status_code==201,r.text
            s=r.json();assert len(s['rows'])==67
            r=c.post(f'/api/statements/{s["id"]}/confirm',headers=h,json={'rows':s['rows']})
            assert r.status_code==200,r.text
            r=c.post('/api/goals',headers=h,json={'name':'Laptop','target_cents':8000000,'saved_cents':1000000,'deadline':(date.today()+timedelta(days=365)).isoformat()})
            assert r.status_code==201,r.text
            d=c.get('/api/dashboard').json()
            assert len(d['months'])==6 and d['transaction_count']==67
            assert d['goals'][0]['milestones'][-1]['saved']==80000
            purchase=c.post('/api/purchase-check',headers=h,json={'amount':1000,'cash_after_bills':3000}).json()
            assert purchase['verdict'] in ('Fits the estimated budget','Need updated statements'),purchase
            chat=c.post('/api/chat',headers=h,json={'message':'Explain my budget'}).json()
            assert 'rule-based' in chat['mode']
            assert c.get(f'/api/statements/{s["id"]}/download').content==content
            assert c.post('/api/auth/logout',headers=h).status_code==200
            assert not c.get('/session').json()['signed_in']
            print(json.dumps({'live_flow':'PASS','confirmed_transactions':d['transaction_count'],
                'complete_months':len(d['months']),'goals':len(d['goals']),'anomalies':len(d['anomalies']),
                'recurring_patterns':len(d['recurring']),'purchase':purchase['verdict']},indent=2))
    except Exception:
        log.flush();log.seek(0);print(log.read())
        raise
    finally:
        # SIGINT lets run.py terminate its backend as well.
        import signal
        if os.name=='nt':
            subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True)
        else:
            proc.send_signal(signal.SIGINT)
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill()
        log.close()
