'use strict';
const $ = (id) => document.getElementById(id);
const tg = window.Telegram?.WebApp;
tg?.ready(); tg?.expand();
try { tg?.setHeaderColor('#f7f8f2'); tg?.setBackgroundColor('#f7f8f2'); } catch {}
function syncViewport() {
  const height = Math.min(window.innerHeight, window.visualViewport?.height || Infinity, tg?.viewportHeight || Infinity);
  document.documentElement.style.setProperty('--app-height', height + 'px');
}
syncViewport();
window.addEventListener('resize', syncViewport);
window.visualViewport?.addEventListener('resize', syncViewport);
tg?.onEvent?.('viewportChanged', syncViewport);
const days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
let cards = [], editing = null, reading = null, repeat = 'daily', toastTimer;
const selectedWeek = new Set(), selectedMonth = new Set();
$('today').textContent = new Intl.DateTimeFormat('ru', {weekday: 'long', day: 'numeric', month: 'long'}).format(new Date()).toUpperCase();

async function api(path, options = {}) {
  const response = await fetch('/api' + path, {...options, headers: {'Content-Type': 'application/json', 'Authorization': 'tma ' + (tg?.initData || ''), ...options.headers}});
  if (!response.ok) {
    let body; try { body = await response.json(); } catch {}
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? 'Проверь название, время, дни повторения и часовой пояс.' : 'Не удалось сохранить изменения. Проверь соединение и попробуй ещё раз.');
  }
  return response.status === 204 ? null : response.json();
}
function el(tag, cls, text) { const node = document.createElement(tag); if (cls) node.className = cls; if (text !== undefined) node.textContent = text; return node; }
function summary(card) {
  const freq = card.repeat === 'daily' ? 'Каждый день' : card.repeat === 'weekly' ? card.weekdays.map(d => days[d]).join(', ') : card.monthdays.join(', ') + ' числа каждого месяца';
  return freq + ' · ' + card.timezone.replaceAll('_', ' ');
}
function dateLabel(value, zone) {
  return new Intl.DateTimeFormat('ru', {timeZone: zone, day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit'}).format(new Date(value));
}
function notify(text) { $('toast').textContent = text; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 3500); }
function showError(id, text) { $(id).textContent = text; $(id).hidden = !text; }
function render() {
  $('cards').replaceChildren(); $('count').textContent = cards.length; $('empty').hidden = cards.length > 0;
  for (const card of cards) {
    const node = el('button', 'card'); node.type = 'button';
    const top = el('div', 'card-top'); top.append(el('span', 'card-icon', card.description ? '✳' : '◷'), el('span', 'arrow', '↗'));
    node.append(top, el('h3', '', card.title), el('p', 'excerpt', card.description || 'Напоминание без описания'));
    const slots = el('div', 'card-bottom'); card.times.forEach(t => slots.append(el('span', 'time-tag', t)));
    node.append(slots, el('div', 'repeat-note', summary(card))); node.onclick = () => openReader(card.id); $('cards').append(node);
  }
  $('next').hidden = !cards.length;
  if (cards.length) {
    const next = [...cards].sort((a,b) => new Date(a.next_at) - new Date(b.next_at))[0];
    $('next-title').textContent = next.title; $('next-time').textContent = dateLabel(next.next_at, next.timezone) + ' · ' + next.timezone;
  }
}
async function load() {
  $('loading').hidden = false; $('retry').hidden = true; showError('load-error', '');
  try { cards = await api('/cards'); render(); return true; }
  catch (err) { showError('load-error', err.message); $('retry').hidden = false; return false; }
  finally { $('loading').hidden = true; }
}
function openReader(id) {
  const card = cards.find(c => c.id === Number(id));
  if (!card) { notify('Карточка удалена или недоступна'); return; }
  reading = card; $('reader-title').textContent = card.title; $('reader-description').textContent = card.description || 'У этой карточки нет описания.';
  $('reader-schedule').textContent = summary(card) + ' · ' + card.times.join(', ');
  $('reader-next').textContent = 'Следующее: ' + dateLabel(card.next_at, card.timezone);
  $('reader').showModal();
}
function addSlot(value = '') {
  if ($('slots').children.length >= 24) return;
  const wrap = el('div', 'slot'), input = el('input'); input.type = 'time'; input.required = true; input.value = value; input.setAttribute('aria-label', 'Время напоминания');
  const remove = el('button', '', '×'); remove.type = 'button'; remove.setAttribute('aria-label', 'Убрать это время');
  remove.onclick = () => { if ($('slots').children.length === 1) { notify('Оставь хотя бы одно время'); return; } wrap.remove(); preview(); };
  input.onchange = preview; wrap.append(input, remove); $('slots').append(wrap); preview();
}
function dayButtons(id, labels, values, selected) {
  $(id).replaceChildren(); labels.forEach((label, index) => {
    const value = values[index], button = el('button', '', label); button.type = 'button'; button.setAttribute('aria-pressed', selected.has(value));
    button.onclick = () => { if (selected.has(value)) selected.delete(value); else selected.add(value); button.setAttribute('aria-pressed', selected.has(value)); preview(); }; $(id).append(button);
  });
}
function setRepeat(value) {
  repeat = value; document.querySelectorAll('[data-repeat]').forEach(b => b.setAttribute('aria-pressed', b.dataset.repeat === value));
  $('week-wrap').hidden = value !== 'weekly'; $('month-wrap').hidden = value !== 'monthly'; preview();
}
function values() { return {title: $('title').value.trim(), description: $('description').value.trim(), times: [...new Set([...$('slots').querySelectorAll('input')].map(i => i.value).filter(Boolean))].sort(), repeat, weekdays: [...selectedWeek].sort((a,b)=>a-b), monthdays: [...selectedMonth].sort((a,b)=>a-b), timezone: $('timezone').value.trim()}; }
function preview() { const data = values(); $('preview').textContent = summary(data) + (data.times.length ? ' · ' + data.times.join(', ') : ' · выбери время'); }
function openEditor(card = null) {
  editing = card?.id ?? null; $('form').reset(); showError('form-error', ''); $('save').disabled = false;
  $('editor-title').textContent = card ? 'Редактировать карточку' : 'Новая карточка'; $('title').value = card?.title || ''; $('description').value = card?.description || '';
  $('timezone').value = card?.timezone || 'Europe/Moscow'; selectedWeek.clear(); selectedMonth.clear();
  (card?.weekdays || []).forEach(d => selectedWeek.add(d)); (card?.monthdays || []).forEach(d => selectedMonth.add(d));
  dayButtons('weekdays', days, [0,1,2,3,4,5,6], selectedWeek); dayButtons('monthdays', Array.from({length:31},(_,i)=>String(i+1)), Array.from({length:31},(_,i)=>i+1), selectedMonth);
  $('slots').replaceChildren(); (card?.times || ['09:00']).forEach(addSlot); setRepeat(card?.repeat || 'daily'); $('editor').showModal(); $('editor').querySelector('.dialog-body').scrollTop = 0;
}
document.querySelectorAll('.close').forEach(b => b.onclick = () => b.closest('dialog').close());
document.querySelectorAll('[data-repeat]').forEach(b => b.onclick = () => setRepeat(b.dataset.repeat));
$('create').onclick = $('create-first').onclick = () => openEditor(); $('add-time').onclick = () => addSlot(); $('timezone').oninput = preview; $('retry').onclick = load;
$('edit').onclick = () => { $('reader').close(); openEditor(reading); };
$('form').onsubmit = async (event) => {
  event.preventDefault(); const data = values();
  if (repeat === 'weekly' && !data.weekdays.length) { showError('form-error', 'Выбери хотя бы один день недели.'); return; }
  if (repeat === 'monthly' && !data.monthdays.length) { showError('form-error', 'Выбери хотя бы одно число месяца.'); return; }
  try { new Intl.DateTimeFormat('ru', {timeZone: data.timezone}); } catch { showError('form-error', 'Выбери существующий часовой пояс, например Europe/Moscow.'); return; }
  $('save').disabled = true; $('save').textContent = 'Сохраняем…'; showError('form-error', '');
  try {
    const saved = await api('/cards' + (editing ? '/' + editing : ''), {method: editing ? 'PUT' : 'POST', body: JSON.stringify(data)});
    cards = cards.filter(c => c.id !== saved.id); cards.push(saved); cards.sort((a,b)=>new Date(a.next_at)-new Date(b.next_at)); render(); $('editor').close(); notify('Карточка сохранена, Муся ♡'); tg?.HapticFeedback?.notificationOccurred('success');
  } catch (err) { showError('form-error', err.message); }
  finally { $('save').disabled = false; $('save').textContent = 'Сохранить карточку'; }
};
$('delete').onclick = async () => {
  if (!reading || !window.confirm('Удалить карточку «' + reading.title + '» и её напоминания?')) return;
  $('delete').disabled = true;
  try { await api('/cards/' + reading.id, {method:'DELETE'}); cards = cards.filter(c => c.id !== reading.id); render(); $('reader').close(); notify('Карточка удалена'); }
  catch(err) { notify(err.message); } finally { $('delete').disabled = false; }
};
for (const dialog of document.querySelectorAll('dialog')) {
  dialog.addEventListener('click', event => { if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close(); } });
}
(async () => {
  try { const config = await api('/config'); $('demo').hidden = !config.demo; } catch {}
  if (await load()) {
    const id = new URLSearchParams(location.search).get('card');
    if (id) openReader(id);
  }
})();
