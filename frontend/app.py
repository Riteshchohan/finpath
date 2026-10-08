import os
import secrets
from datetime import timedelta
import httpx
from flask import Flask, Response, render_template, request, session, jsonify
from backend.storage import secret

app = Flask(__name__)
app.secret_key = secret('web-session.key')
app.config.update(MAX_CONTENT_LENGTH=11*1024*1024, SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE')=='1',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
API = os.getenv('API_URL','http://127.0.0.1:8000')

@app.get('/')
def index():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(24)
    return render_template('index.html', csrf=session['csrf'])

@app.get('/session')
def session_status():
    return {'signed_in':bool(session.get('token')),'email':session.get('email','')}

@app.route('/api/<path:path>',methods=['GET','POST','PUT','PATCH','DELETE'])
def proxy(path):
    if request.method!='GET' and not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),session.get('csrf','missing')):
        return jsonify(detail='Security token expired. Refresh this page.'),403
    headers = {'Authorization':'Bearer '+session['token']} if session.get('token') else {}
    kwargs = {}
    if request.files:
        kwargs['files'] = {k:(f.filename,f.stream,f.mimetype) for k,f in request.files.items()}
        kwargs['data'] = request.form.to_dict()
    elif request.is_json:
        kwargs['json'] = request.get_json()
    try:
        r = httpx.request(request.method,API+'/'+path,headers=headers,params=request.args,timeout=180,trust_env=False,**kwargs)
    except httpx.HTTPError:
        return jsonify(detail='Backend unavailable. Start the website with python run.py.'),503
    if path=='auth/login' and r.status_code==200:
        data = r.json()
        session['token'],session['email'] = data['token'],data['email']
        session.permanent = True
        return {'email':data['email']}
    if path=='auth/logout':
        session.pop('token',None)
        session.pop('email',None)
    out = Response(r.content,status=r.status_code,content_type=r.headers.get('content-type','application/json'))
    if 'content-disposition' in r.headers:
        out.headers['Content-Disposition'] = r.headers['content-disposition']
    return out

@app.after_request
def secure_headers(response):
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Cache-Control']='no-store'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    return response

@app.errorhandler(413)
def too_large(error):
    return jsonify(detail='Maximum statement file size is 10 MB.'),413
