"""Auth boundary checks simulate Supabase; never send real emails."""
import pytest
from app.core.config import get_settings
from app.api.routes import auth
OWNER = {"id":"owner-id","email":"owner@example.com","email_confirmed_at":"2026-09-11", "user_metadata":{"full_name":"Owner"}}
@pytest.fixture
def secured(monkeypatch):
    s=get_settings()
    monkeypatch.setattr(s,'auth_required',True)
    monkeypatch.setattr(s,'cors_allowed_origins',['http://localhost:5174'])
    from app.database import SessionLocal
    from app.models.business import Business, BusinessMember, LEGACY_BUSINESS_ID
    with SessionLocal() as db:
        db.add(Business(id=LEGACY_BUSINESS_ID,name='Owner business'))
        db.flush()
        db.add(BusinessMember(business_id=LEGACY_BUSINESS_ID,user_id='owner-id',role='owner'))
        db.commit()
@pytest.fixture
def origin(): return {'origin':'http://localhost:5174'}
@pytest.mark.parametrize('path',['/api/sales','/api/dashboard','/api/assistant','/api/system','/uploads/private.png'])
def test_anonymous_rejected(client,secured,path):
    assert client.get(path).status_code==401

def test_csrf(client,secured):
    assert client.post('/api/auth/login',json={'email':'a@b.com','password':'password'},headers={'origin':'https://evil.example'}).status_code==403

def test_health_public(client,secured):
    assert client.get('/api/health').status_code==200
@pytest.mark.parametrize('confirmed,email,expected',[(True,'owner@example.com',True),(False,'owner@example.com',False),(True,'other@example.com',False)])
def test_verified_membership(secured,confirmed,email,expected):
    assert auth.user_view({**OWNER,'id':'owner-id' if email=='owner@example.com' else 'other-id','email':email,'email_confirmed_at':'yes' if confirmed else None})['has_workspace'] is expected

def test_signup_confirmation(client,secured,origin,monkeypatch):
    async def fake(*args,**kwargs): return {'id':'new-user'}
    monkeypatch.setattr(auth,'auth_request',fake)
    r=client.post('/api/auth/signup',json={'email':'new@example.com','password':'strongpassword'},headers=origin)
    assert r.status_code==200
    assert r.json()=={'user':None,'confirmation_required':True}
    assert 'sydney_access' not in client.cookies

def test_login_refresh_logout(client,secured,origin,monkeypatch):
    calls=[]
    async def fake(method,path,payload=None,token=None):
        calls.append(path)
        if path=='user': return OWNER
        if path=='logout': return {}
        return {'user':OWNER,'access_token':'access','refresh_token':'refresh','expires_in':3600}
    monkeypatch.setattr(auth,'auth_request',fake)
    r=client.post('/api/auth/login',json={'email':'owner@example.com','password':'password'},headers=origin)
    assert r.status_code==200 and r.json()['user']['has_workspace']
    assert 'access_token' not in r.json()
    assert all('HttpOnly' in c and 'SameSite=lax' in c for c in r.headers.get_list('set-cookie'))
    assert client.get('/api/auth/session').json()['user']['email']=='owner@example.com'
    assert client.post('/api/auth/refresh',headers=origin).status_code==200
    assert client.post('/api/auth/logout',headers=origin).status_code==200
    assert client.get('/api/auth/session').status_code==401
    assert 'logout' in calls

def test_staff_login_alias_is_mapped_to_private_auth_email(client, secured, origin, monkeypatch):
    staff = {**OWNER, "id": "staff-id", "email": "liad@support.sydneyexpenses.com"}
    from app.database import SessionLocal
    from app.models.business import AppAccount
    with SessionLocal() as db:
        db.add(AppAccount(user_id="staff-id", email="liad@support", system_role="support"))
        db.commit()

    async def fake(method, path, payload=None, token=None):
        assert payload["email"] == "liad@support.sydneyexpenses.com"
        return {"user": staff, "access_token": "access", "refresh_token": "refresh", "expires_in": 3600}

    monkeypatch.setattr(auth, "auth_request", fake)
    response = client.post('/api/auth/login', json={'email':'liad@support','password':'password'}, headers=origin)
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "liad@support"
    assert response.json()["user"]["system_role"] == "support"

def test_other_user_denied(client,secured,monkeypatch):
    async def fake(*args,**kwargs): return {**OWNER,'id':'other-id','email':'other@example.com'}
    monkeypatch.setattr(auth,'auth_request',fake)
    client.cookies.set('sydney_access','other')
    assert client.get('/api/sales').status_code==403

def test_webhook_signature_boundary(client,secured):
    r=client.post('/api/webhooks/payments',json={})
    assert r.status_code in (400,401,503)
    assert r.json()['detail']!='יש להתחבר כדי להמשיך'

def test_login_is_rate_limited_per_ip(client,secured,origin,monkeypatch):
    async def fake(*args,**kwargs): raise __import__('fastapi').HTTPException(401,'לא ניתן להשלים את הבקשה. בדקו את הפרטים ונסו שוב.')
    monkeypatch.setattr(auth,'auth_request',fake)
    responses=[client.post('/api/auth/login',json={'email':f'attacker{i}@example.com','password':'wrong'},headers=origin) for i in range(16)]
    assert [r.status_code for r in responses[:15]].count(429)==0
    assert responses[15].status_code==429

def test_login_is_rate_limited_per_email_even_under_the_per_ip_ceiling(client,secured,origin,monkeypatch):
    # 6 attempts against ONE email stays well under the per-IP ceiling (15)
    # but exceeds the stricter per-email one (5) — this is what stops a
    # distributed-IP brute force against one known account, which a
    # per-IP-only limiter would never catch.
    async def fake(*args,**kwargs): raise __import__('fastapi').HTTPException(401,'לא ניתן להשלים את הבקשה. בדקו את הפרטים ונסו שוב.')
    monkeypatch.setattr(auth,'auth_request',fake)
    responses=[client.post('/api/auth/login',json={'email':'victim@example.com','password':'wrong'},headers=origin) for _ in range(6)]
    assert responses[5].status_code==429

def test_signup_is_rate_limited_per_ip(client,secured,origin,monkeypatch):
    async def fake(*args,**kwargs): return {'id':'new-user'}
    monkeypatch.setattr(auth,'auth_request',fake)
    responses=[client.post('/api/auth/signup',json={'email':f'new{i}@example.com','password':'strongpassword'},headers=origin) for i in range(6)]
    assert responses[5].status_code==429

def test_rate_limit_response_leaks_no_internal_detail(client,secured,origin,monkeypatch):
    async def fake(*args,**kwargs): return {'id':'new-user'}
    monkeypatch.setattr(auth,'auth_request',fake)
    for i in range(5):
        client.post('/api/auth/signup',json={'email':f'x{i}@example.com','password':'strongpassword'},headers=origin)
    r=client.post('/api/auth/signup',json={'email':'x5@example.com','password':'strongpassword'},headers=origin)
    assert r.status_code==429
    assert r.json()=={'detail':'יותר מדי ניסיונות. נסו שוב בעוד מספר דקות.'}
