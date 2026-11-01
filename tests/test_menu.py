import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from test_app import signed


@pytest.fixture
def client(tmp_path):
    app = create_app(database_url=f"sqlite:///{tmp_path / 'menu.db'}", bot_token="test-token", dev_mode=False)
    with TestClient(app) as c:
        c.headers.update(signed())
        yield c


def dish(**kw):
    return {"title": "Лазанья с индейкой", "category": "Основные блюда", "calories": 200, "protein": 15, "fat": 9, "carbs": 14, **kw}


def add(client, ident, day="2026-11-04", meal="lunch", grams=250):
    r = client.post('/api/menu/entries', json={"dish_id": ident, "day": day, "meal": meal, "grams": grams})
    assert r.status_code == 201, r.text
    return r.json()


def test_dishes_catalog_and_ownership(client):
    r = client.post('/api/menu/dishes', json=dish(note="Рецепт", recipe_url="https://example.com/recipe"))
    assert r.status_code == 201
    ident = r.json()['id']
    assert client.get('/api/menu/dishes').json()[0]['protein'] == 15
    assert client.get('/api/menu/dishes', headers=signed(99)).json() == []
    assert client.put(f'/api/menu/dishes/{ident}', headers=signed(99), json=dish()).status_code == 404
    assert client.put(f'/api/menu/dishes/{ident}', json=dish(favorite=True)).json()['favorite'] is True
    assert client.delete(f'/api/menu/dishes/{ident}', headers=signed(99)).status_code == 404
    assert client.delete(f'/api/menu/dishes/{ident}').status_code == 204


def test_portions_move_totals_and_snapshot(client):
    ident = client.post('/api/menu/dishes', json=dish()).json()['id']
    entry = add(client, ident)
    assert entry['nutrition'] == {'calories': 500, 'protein': 37.5, 'fat': 22.5, 'carbs': 35}
    r = client.patch(f"/api/menu/entries/{entry['id']}", json={"grams": 180, "meal": "dinner"})
    assert r.json()['nutrition']['calories'] == 360
    add(client, ident, grams=100)
    client.put(f'/api/menu/dishes/{ident}', json=dish(calories=900))
    client.delete(f'/api/menu/dishes/{ident}')
    days = client.get('/api/menu/plan?start=2026-11-02').json()['days']
    assert len(days) == 7
    assert days[0]['totals']['calories'] == 0
    assert days[2]['totals']['calories'] == 560
    assert days[2]['meals']['dinner']['totals']['calories'] == 360
    assert days[2]['meals']['dinner']['entries'][0]['title'] == 'Лазанья с индейкой'


def test_copy_meal_day_week_and_clear(client):
    ident = client.post('/api/menu/dishes', json=dish()).json()['id']
    add(client, ident)
    add(client, ident, meal='breakfast', grams=100)
    add(client, ident, day='2026-11-05', grams=10)
    payload = {'source': '2026-11-04', 'target': '2026-11-05', 'scope': 'meal', 'source_meal': 'lunch', 'target_meal': 'dinner'}
    assert client.post('/api/menu/copy', json=payload).json()['copied'] == 1
    assert client.post('/api/menu/copy', json={**payload, 'scope': 'day'}).json()['copied'] == 2
    assert client.post('/api/menu/copy', json={**payload, 'target': '2026-11-04', 'scope': 'day'}).status_code == 422
    assert client.post('/api/menu/copy', json={'source':'2026-11-02', 'target':'2026-11-09', 'scope':'week'}).json()['copied'] == 4
    week = client.get('/api/menu/plan?start=2026-11-09').json()['days']
    assert week[2]['totals']['calories'] == 700
    assert week[3]['totals']['calories'] == 700
    assert client.delete('/api/menu/day/2026-11-11').status_code == 204
    assert client.get('/api/menu/plan?start=2026-11-09').json()['days'][2]['totals']['calories'] == 0


@pytest.mark.parametrize('change', [{'calories':-1}, {'title':' '}, {'protein':-2}, {'recipe_url':'javascript:alert(1)'}, {'photo':'data:text/html;base64,AA=='}, {'category':'oops'}])
def test_invalid_dishes(client, change):
    assert client.post('/api/menu/dishes', json=dish(**change)).status_code == 422


def test_invalid_portions_and_foreign_entries(client):
    ident = client.post('/api/menu/dishes', json=dish()).json()['id']
    assert client.post('/api/menu/entries', headers=signed(99), json={'dish_id':ident,'day':'2026-11-04','meal':'lunch','grams':100}).status_code == 404
    entry = add(client, ident)
    for grams in (0, -10, 'NaN'):
        assert client.patch(f"/api/menu/entries/{entry['id']}", json={'grams':grams,'meal':'lunch'}).status_code == 422
    assert client.patch(f"/api/menu/entries/{entry['id']}", headers=signed(99), json={'grams':100,'meal':'lunch'}).status_code == 404
    assert client.delete(f"/api/menu/entries/{entry['id']}", headers=signed(99)).status_code == 404
    assert client.get('/api/menu/plan?start=2026-11-02', headers=signed(99)).json()['days'][2]['totals']['calories'] == 0


def test_settings_persist_and_do_not_block_target(client):
    assert client.get('/api/menu/settings').json() == {'calorie_goal':None,'theme':'light','decimals':1}
    assert client.put('/api/menu/settings', json={'calorie_goal':100,'theme':'dark','decimals':0}).status_code == 200
    assert client.get('/api/menu/settings').json()['theme'] == 'dark'
    assert client.get('/api/menu/settings', headers=signed(99)).json()['theme'] == 'light'
    ident = client.post('/api/menu/dishes', json=dish()).json()['id']
    assert add(client, ident)['nutrition']['calories'] == 500


def test_data_survives_app_restart(tmp_path):
    url = f"sqlite:///{tmp_path / 'persistent.db'}"
    with TestClient(create_app(database_url=url, bot_token='test-token', dev_mode=False)) as c:
        c.headers.update(signed())
        ident = c.post('/api/menu/dishes', json=dish()).json()['id']
        add(c, ident)
    with TestClient(create_app(database_url=url, bot_token='test-token', dev_mode=False)) as c:
        c.headers.update(signed())
        assert c.get('/api/menu/dishes').json()[0]['id'] == ident
        assert c.get('/api/menu/plan?start=2026-11-02').json()['days'][2]['totals']['calories'] == 500


def test_photo_and_unrounded_totals(client):
    photo='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jF9sAAAAASUVORK5CYII='
    r=client.post('/api/menu/dishes', json=dish(photo=photo, calories=.14))
    assert r.status_code == 201
    assert client.get('/api/menu/dishes').json()[0]['photo'] == photo
    add(client,r.json()['id'],grams=100)
    add(client,r.json()['id'],grams=100)
    assert client.get('/api/menu/plan?start=2026-11-02').json()['days'][2]['totals']['calories'] == .28


def test_copy_isolation_and_entry_deletion(client):
    ident=client.post('/api/menu/dishes',json=dish()).json()['id']
    entry=add(client,ident)
    r=client.post('/api/menu/copy',headers=signed(99),json={'source':'2026-11-04','target':'2026-11-05','scope':'day'})
    assert r.json()['copied'] == 0
    assert client.get('/api/menu/plan?start=2026-11-02').json()['days'][2]['totals']['calories'] == 500
    assert client.delete('/api/menu/entries/'+str(entry['id'])).status_code == 204
    assert client.get('/api/menu/plan?start=2026-11-02').json()['days'][2]['totals']['calories'] == 0
