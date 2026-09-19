from decimal import Decimal
from unittest.mock import patch
import pytest
from sqlalchemy import select, delete, func, insert, text
from app.database import SessionLocal
from app.models.business import Business, BusinessMember, BusinessPaymentProvider
from app.models.sale import Sale
from app.models.sale_event import SaleEvent
from app.api.routes import auth
from app.core.config import get_settings
from app.core import tenant

@pytest.fixture
def businesses(monkeypatch):
    monkeypatch.setattr(get_settings(),'auth_required',True)
    monkeypatch.setattr(get_settings(),'cors_allowed_origins',['http://localhost:5174'])
    with SessionLocal() as db:
        db.add_all([Business(id='a',name='Business A'),Business(id='b',name='Business B')]);db.flush()
        db.add_all([BusinessMember(business_id='a',user_id='user-a',role='owner'),BusinessMember(business_id='b',user_id='user-b',role='viewer')])
        for bid in ['a','b']:
            db.add(Sale(id='sale-'+bid,business_id=bid,customer_name=bid,service_name='Consulting',gross_amount=Decimal('118'),net_amount=Decimal('100'),document_url='/uploads/'+bid+'.png'))
        db.commit()
    async def fake(method,path,payload=None,token=None):
        return {'id':token,'email':token+'@example.com','email_confirmed_at':'yes','user_metadata':{}}
    monkeypatch.setattr(auth,'auth_request',fake)

def test_session_queries_and_writes_are_scoped(businesses):
    with SessionLocal() as db:
        db.info['business_id']='a'
        assert db.get(Sale,'sale-b') is None
        assert db.scalar(select(func.count()).select_from(Sale))==1
        assert [s.id for s in db.scalars(select(Sale))]==['sale-a']
        db.execute(delete(Sale));db.commit()
    with SessionLocal() as db:
        assert db.get(Sale,'sale-b') is not None

def test_cross_business_write_rejected(businesses):
    with SessionLocal() as db:
        db.info['business_id']='a'
        db.add(Sale(business_id='b',customer_name='x',service_name='x',gross_amount=1,net_amount=1))
        with pytest.raises(ValueError): db.commit()

def test_raw_sql_and_bulk_insert_are_blocked_in_scoped_sessions(businesses):
    with SessionLocal() as db:
        db.info['business_id']='a'
        with pytest.raises(ValueError, match='Raw SQL'):
            db.execute(text('SELECT * FROM sales'))
        with pytest.raises(ValueError, match='Bulk ORM inserts'):
            db.execute(insert(Sale), [{'customer_name':'x','service_name':'x','gross_amount':1,'net_amount':1}])

def test_api_sales_events_uploads_and_viewer(client,businesses):
    client.cookies.set('sydney_access','user-a')
    assert [s['id'] for s in client.get('/api/sales').json()]==['sale-a']
    assert client.get('/api/sales/sale-b').status_code==404
    assert client.get('/api/sales/sale-b/events').status_code==404
    assert client.get('/uploads/b.png').status_code==404
    assert client.delete('/api/sales/sale-b',headers={'origin':'http://localhost:5174'}).status_code==404
    client.cookies.set('sydney_access','user-b')
    assert client.get('/api/sales').status_code==200
    assert client.delete('/api/sales/sale-b',headers={'origin':'http://localhost:5174'}).status_code==403

def test_onboarding_identity_and_duplicate_guard(client,businesses):
    client.cookies.set('sydney_access','new-user')
    headers={'origin':'http://localhost:5174'}
    assert client.get('/api/sales').status_code==403
    assert client.post('/api/businesses',json={'name':'New business','user_id':'user-a'},headers=headers).status_code==422
    r=client.post('/api/businesses',json={'name':'New business','payment_providers':['grow','cardcom']},headers=headers)
    assert r.status_code==201
    assert client.get('/api/auth/session').json()['user']['has_workspace']
    assert client.get('/api/sales').json()==[]
    assert client.post('/api/businesses',json={'name':'Again'},headers=headers).status_code==409
    with SessionLocal() as db:
        assert db.get(Business,r.json()['id']).country_code=='IL'
        assert set(db.scalars(select(BusinessPaymentProvider.provider).where(
            BusinessPaymentProvider.business_id == r.json()['id']
        )).all()) == {'grow', 'cardcom'}

def test_same_external_id_allowed_in_different_businesses(businesses):
    for bid in ['a','b']:
        with SessionLocal() as db:
            db.info['business_id']=bid
            sale=Sale(customer_name='x',service_name='x',gross_amount=1,net_amount=1,source_provider='demo-pay',external_id='shared')
            db.add(sale);db.commit()
            assert sale.business_id==bid

def test_assistant_conversations_are_private_to_each_user_and_business(client,businesses,monkeypatch):
    monkeypatch.setattr(get_settings(),'openai_api_key','sk-test-not-real')
    headers={'origin':'http://localhost:5174'}
    with patch('app.api.routes.assistant.answer_question',return_value='ok'):
        client.cookies.set('sydney_access','user-a')
        created=client.post('/api/assistant/chat',json={'message':'private question'},headers=headers)
        assert created.status_code==200
        assert len(client.get('/api/assistant/conversations').json())==1

        client.cookies.clear()
        client.cookies.set('sydney_access','user-b')
        assert client.get('/api/assistant/conversations').json()==[]
        assert client.get('/api/assistant/conversations/'+created.json()['conversation_id']).status_code==404
