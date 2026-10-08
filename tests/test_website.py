import io
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from backend import main
from backend.storage import db, cipher
from backend.parser import extract, money
from backend.planner import dashboard, complete_months

CSV = b'date,description,debit,credit\n2026-01-01,Salary,,50000\n2026-01-03,Rent,12000,\n2026-01-05,Groceries,4000,\n2026-01-15,Self transfer,10000,\n'

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('FINPATH_DATA',str(tmp_path))
    monkeypatch.setenv('ENABLE_HF','0')
    monkeypatch.setenv('CHAT_PROVIDER','local')
    main.attempts.clear()
    with TestClient(main.app) as client:
        yield client

def account(client,email='one@example.com'):
    payload={'email':email,'password':'test-password-123'}
    assert client.post('/auth/register',json=payload).status_code==201
    r = client.post('/auth/login',json=payload)
    assert r.status_code==200
    return {'Authorization':'Bearer '+r.json()['token']}

def upload(client,h,content=CSV):
    return client.post('/statements',headers=h,files={'file':('bank.csv',content,'text/csv')},
                       data={'start_date':'2026-01-01','end_date':'2026-01-31'})

def test_full_import_goal_and_delete(client):
    h=account(client)
    response=upload(client,h)
    assert response.status_code==201,response.text
    s=response.json()
    assert client.get('/dashboard',headers=h).json()['transaction_count']==0
    assert client.post(f'/statements/{s["id"]}/confirm',headers=h,json={'rows':s['rows']}).status_code==200
    d=client.get('/dashboard',headers=h).json()
    assert d['months'][0]['income']==50000
    assert d['months'][0]['expense']==16000
    deadline=(date.today()+timedelta(days=365)).isoformat()
    g=client.post('/goals',headers=h,json={'name':'Laptop','target_cents':6000000,'saved_cents':0,'deadline':deadline})
    assert g.status_code==201
    d=client.get('/dashboard',headers=h).json()
    assert 4990<d['required_monthly']<5010
    assert d['goals'][0]['milestones'][-1]['saved']==60000
    assert d['goals'][0]['milestones'][-1]['date']==deadline
    assert client.get(f'/statements/{s["id"]}/download',headers=h).content==CSV
    with db() as c:
        stored=c.execute('SELECT content FROM statements').fetchone()[0]
    assert b'Salary' not in stored and cipher().decrypt(stored)==CSV
    assert client.delete(f'/statements/{s["id"]}',headers=h).status_code==200
    assert client.get('/transactions',headers=h).json()==[]

def test_user_isolation(client):
    a,b=account(client),account(client,'two@example.com')
    s=upload(client,a).json()
    for method,path,body in [('get',f'/statements/{s["id"]}/download',None),('delete',f'/statements/{s["id"]}',None),
                             ('post',f'/statements/{s["id"]}/confirm',{'rows':s['rows']})]:
        kwargs={'headers':b}
        if body:kwargs['json']=body
        assert getattr(client,method)(path,**kwargs).status_code==404
    assert client.get('/statements',headers=b).json()==[]
    assert client.get('/dashboard').status_code==401

def test_duplicate_overlap_and_confirm_validation(client):
    h=account(client);s=upload(client,h).json()
    assert upload(client,h).status_code==409
    bad=[dict(s['rows'][0],date='2026-02-01')]
    assert client.post(f'/statements/{s["id"]}/confirm',headers=h,json={'rows':bad}).status_code==422
    assert client.post(f'/statements/{s["id"]}/confirm',headers=h,json={'rows':s['rows']}).status_code==200
    assert client.post(f'/statements/{s["id"]}/confirm',headers=h,json={'rows':s['rows']}).status_code==409

def test_auth_logout(client):
    h=account(client)
    assert client.post('/auth/login',json={'email':'one@example.com','password':'incorrect-password'}).status_code==401
    assert client.post('/auth/logout',headers=h).status_code==200
    assert client.get('/dashboard',headers=h).status_code==401

def test_goal_validation_and_cross_user(client):
    a,b=account(client),account(client,'two@example.com')
    goal={'name':'Trip','target_cents':100000,'saved_cents':0,'deadline':(date.today()+timedelta(days=30)).isoformat()}
    gid=client.post('/goals',headers=a,json=goal).json()['id']
    assert client.put(f'/goals/{gid}',headers=b,json=goal).status_code==404
    assert client.delete(f'/goals/{gid}',headers=b).status_code==404
    assert client.post('/goals',headers=a,json={**goal,'saved_cents':200000}).status_code==422
    assert client.post('/goals',headers=a,json={**goal,'deadline':date.today().isoformat()}).status_code==422

def test_empty_purchase_and_chat(client):
    h=account(client)
    r=client.post('/purchase-check',headers=h,json={'amount':100,'cash_after_bills':1000}).json()
    assert r['verdict']=='Need updated statements'
    r=client.post('/chat',headers=h,json={'message':'What is my budget?'}).json()
    assert 'complete historical month' in r['answer'] and 'rule-based' in r['mode']

def test_complete_period_and_transfer_exclusion():
    rows=[dict(date='2026-01-05',amount_cents=500000,category='Income',essential=False),
          dict(date='2026-01-07',amount_cents=900000,category='Transfer',essential=False)]
    partial=[dict(start_date='2026-01-05',end_date='2026-01-31')]
    assert complete_months(rows,partial,date(2026,2,8))==[]
    full=[dict(start_date='2026-01-01',end_date='2026-01-31')]
    assert complete_months(rows,full,date(2026,2,8))[0]['income']==5000

def test_multiple_goals_do_not_reuse_income(monkeypatch):
    monkeypatch.setenv('ENABLE_HF','0')
    rows=[dict(date='2026-01-01',description='Pay',amount_cents=1000000,category='Income',essential=False)]
    statements=[dict(start_date='2026-01-01',end_date='2026-01-31')]
    goals=[dict(id=i,name='Goal',target_cents=2000000,saved_cents=0,deadline='2026-03-01') for i in [1,2]]
    d=dashboard(rows,statements,goals,date(2026,2,1))
    assert not d['feasible'] and d['monthly_shortfall']>30000
    assert d['required_monthly']==sum(g['monthly_saving'] for g in d['goals'])
    assert d['remaining_month_budget']==0

def test_csv_parser_and_money():
    rows,warnings=extract('bank.csv',CSV)
    assert len(rows)==4 and not warnings
    assert rows[1]['amount_cents']==-1200000
    assert money('₹1,23,456.78')==12345678
    with pytest.raises(ValueError):money('NaN')
    with pytest.raises(ValueError):extract('old.doc',b'old')
    with pytest.raises(ValueError):extract('fake.pdf',b'not a PDF')
    rows,warnings=extract('bank.csv',b'date,description,debit,credit\n2026-01-01,Bad,10,20\n')
    assert not rows and warnings
    rows,_=extract('bank.csv',b'Date,Particulars,Withdrawal,Deposit\n01/01/2026,Salary,,50000\n')
    assert len(rows)==1

def test_hf_adapter_contract(monkeypatch):
    # Exercise current pipeline calling convention and output dimensions without downloading weights.
    import sys
    import types
    import numpy as np
    from backend import ml
    class Tensor:
        def detach(self):return self
        def cpu(self):return self
        def numpy(self):return np.array([[[40000,50000,60000]],[[20000,25000,30000]]])
    class Pipeline:
        def predict_quantiles(self, inputs, prediction_length, quantile_levels):
            assert inputs.shape==(2,3) and prediction_length==1 and quantile_levels==[.1,.5,.9]
            return Tensor(),None
    monkeypatch.setenv('ENABLE_HF','1')
    monkeypatch.setitem(sys.modules,'torch',types.SimpleNamespace(tensor=lambda x,dtype:x,float32='float32'))
    monkeypatch.setattr(ml,'forecaster',lambda:Pipeline())
    result=ml.forecast([{'income':50000,'expense':25000}]*3)
    assert result['income']==50000 and result['conservative_income']==40000
    assert 'chronos-bolt' in result['method']

def test_docx_parser():
    from docx import Document
    d=Document();t=d.add_table(rows=1,cols=4)
    for c,v in zip(t.rows[0].cells,['Date','Description','Debit','Credit']):c.text=v
    for c,v in zip(t.add_row().cells,['01/01/2026','Salary','','50000']):c.text=v
    out=io.BytesIO();d.save(out)
    rows,warnings=extract('statement.docx',out.getvalue())
    assert len(rows)==1 and rows[0]['amount_cents']==5000000

def test_pdf_parser():
    reportlab=pytest.importorskip('reportlab')
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    from reportlab.lib import colors
    b=io.BytesIO();doc=SimpleDocTemplate(b)
    t=Table([['Date','Description','Debit','Credit'],['01/01/2026','Salary','','50000']],colWidths=[90,160,90,90])
    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.5,colors.black)]))
    doc.build([t])
    rows,warnings=extract('bank.pdf',b.getvalue())
    assert len(rows)==1 and rows[0]['amount_cents']==5000000

def test_frontend_csrf_and_headers(client):
    from frontend.app import app
    web=app.test_client()
    response=web.get('/')
    assert response.status_code==200 and b'FinPath' in response.data
    assert "script-src 'self'" in response.headers['Content-Security-Policy']
    assert web.post('/api/auth/login',json={}).status_code==403

def test_remote_chat_requires_consent(client,monkeypatch):
    h=account(client)
    monkeypatch.setenv('CHAT_PROVIDER','groq');monkeypatch.setenv('GROQ_API_KEY','not-a-real-key')
    def forbidden(*args,**kwargs):raise AssertionError('No outbound call permitted without consent')
    monkeypatch.setattr(main.httpx,'post',forbidden)
    assert 'Local' in client.post('/chat',headers=h,json={'message':'Explain budget','external_consent':False}).json()['mode']

def test_anomaly_detector():
    from backend.ml import anomalies
    rows=[dict(date='2026-01-01',description='Shopping',amount_cents=-(10000+i*100),category='Shopping') for i in range(30)]
    rows.append(dict(date='2026-01-20',description='Large purchase',amount_cents=-2000000,category='Shopping'))
    assert any(r['description']=='Large purchase' for r in anomalies(rows))
