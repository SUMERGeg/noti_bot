from fastapi.testclient import TestClient
import pytest
from app.main import create_app
from test_app import signed


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(database_url=f"sqlite:///{tmp_path/'diary.db'}",bot_token='test-token',dev_mode=False)) as c:
        c.headers.update(signed())
        yield c


def test_crud_week_and_ownership(client):
    assert client.get('/api/achievements?start=2026-11-02',headers={'Authorization':''}).status_code == 401
    for day in ['2026-11-02','2026-11-02','2026-11-08','2026-11-09']:
        r=client.post('/api/achievements',json={'day':day,'text':'  Похвалила себя  '})
        assert r.status_code == 201
    records=client.get('/api/achievements?start=2026-11-02').json()
    assert len(records)==3
    assert records[0]['text']=='Похвалила себя'
    assert client.get('/api/achievements?start=2026-11-02',headers=signed(99)).json()==[]
    ident=records[0]['id']
    assert client.put(f'/api/achievements/{ident}',headers=signed(99),json={'text':'Чужая'}).status_code==404
    assert client.delete(f'/api/achievements/{ident}',headers=signed(99)).status_code==404
    assert client.put(f'/api/achievements/{ident}',json={'text':'Ела не торопясь'}).json()['text']=='Ела не торопясь'
    assert client.delete(f'/api/achievements/{ident}').status_code==204
    assert len(client.get('/api/achievements?start=2026-11-02').json())==2


def test_empty_text_and_menu_clear_are_independent(client):
    assert client.post('/api/achievements',json={'day':'2026-11-03','text':'   '}).status_code==422
    client.post('/api/achievements',json={'day':'2026-11-03','text':'Составила меню'})
    client.delete('/api/menu/day/2026-11-03')
    assert len(client.get('/api/achievements?start=2026-11-02').json())==1


def test_persistence(tmp_path):
    url=f"sqlite:///{tmp_path/'saved.db'}"
    for first in (True,False):
        with TestClient(create_app(database_url=url,bot_token='test-token',dev_mode=False)) as c:
            c.headers.update(signed())
            if first:c.post('/api/achievements',json={'day':'2026-11-03','text':'Прислушалась к себе'})
            assert c.get('/api/achievements?start=2026-11-02').json()[0]['text']=='Прислушалась к себе'
