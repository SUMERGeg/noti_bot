'use strict';
(() => {
  let context=null,records=[],sequence=0;
  const dialog=el('dialog');dialog.setAttribute('aria-labelledby','achievement-title');document.body.append(dialog);
  const button=(text,cls,fn)=>{const b=el('button',cls,text);b.type='button';b.onclick=fn;return b;};
  const dateLabel=day=>new Intl.DateTimeFormat('ru',{day:'numeric',month:'long'}).format(MenuCore.parse(day));
  function edit(record=null){
    const day=record?.day||context.date,form=el('form','dialog-content'),head=el('div','dialog-head');
    const title=el('h2','',record?'Моё достижение':'Похвалить себя 🌸');title.id='achievement-title';
    const close=button('×','icon-button',()=>dialog.close());close.setAttribute('aria-label','Закрыть');head.append(title,close);
    const body=el('div','dialog-body'),label=el('label','','За что я могу себя похвалить?'),text=el('textarea');text.id='achievement-text';label.htmlFor=text.id;text.rows=5;text.required=true;text.maxLength=5000;text.value=record?.text||'';text.placeholder='Например, сегодня ела сидя и не торопилась.';
    const error=el('p','error');error.hidden=true;error.setAttribute('role','alert');
    body.append(el('p','hint',dateLabel(day)),label,text,el('p','hint','Можно заметить даже маленький шаг, Муся. Записывай, когда хочется ♡'),error);
    const actions=el('div','form-actions'),save=button('Сохранить','button primary');save.type='submit';actions.append(button('Отмена','button secondary',()=>dialog.close()),save);form.append(head,body,actions);
    form.onsubmit=async event=>{event.preventDefault();if(!text.value.trim()){error.textContent='Напиши несколько слов о своём достижении.';error.hidden=false;return;}save.disabled=true;error.hidden=true;try{await api('/achievements'+(record?'/'+record.id:''),{method:record?'PUT':'POST',body:JSON.stringify(record?{text:text.value.trim()}:{day,text:text.value.trim()})});dialog.close();notify('Твой маленький успех сохранён 🌸');await refresh(context);}catch(e){error.textContent=e.message;error.hidden=false;}finally{save.disabled=false;}};
    dialog.replaceChildren(form);dialog.showModal();
  }
  async function remove(record,btn){
    if(!confirm('Удалить эту запись из дневника?'))return;
    btn.disabled=true;try{await api('/achievements/'+record.id,{method:'DELETE'});await refresh(context);}catch(e){notify(e.message);}finally{btn.disabled=false;}
  }
  function card(title){const c=el('section','achievement-card');c.append(el('h3','',title));return c;}
  function render(){
    document.querySelectorAll('[data-diary-block]').forEach(n=>n.remove());
    document.querySelectorAll('#menu-days [data-day]').forEach(b=>{
      b.querySelector('.achievement-flower')?.remove();
      if(records.some(r=>r.day===b.dataset.day)){const flower=el('span','achievement-flower','🌸');flower.setAttribute('aria-hidden','true');b.append(flower);}
    });
    if(!context.overview){
      const daily=card('🌸 Мои достижения');daily.dataset.diaryBlock='day';daily.append(el('p','hint','За что я могу себя сегодня похвалить?'));
      for(const r of records.filter(r=>r.day===context.date)){
        const row=el('div','achievement-row'),actions=el('div','entry-actions'),change=button('✎','icon-button',()=>edit(r)),del=button('×','icon-button');del.onclick=()=>remove(r,del);change.setAttribute('aria-label','Редактировать достижение');del.setAttribute('aria-label','Удалить достижение');actions.append(change,del);row.append(el('p','achievement-text',r.text),actions);daily.append(row);
      }
      daily.append(button('＋ Добавить достижение','text-button',()=>edit()));$('day-plan').append(daily);
    }
    const weekly=card('Мои успехи за неделю');weekly.dataset.diaryBlock='week';weekly.append(el('p','hint','Записанных достижений: '+records.length));
    if(!records.length)weekly.append(el('p','hint','Здесь можно собирать тёплые слова о себе — когда захочется ♡'));
    for(const r of records){const row=el('div','achievement-week-row'),open=button('🌸 '+dateLabel(r.day),'text-button',()=>window.dispatchEvent(new CustomEvent('menu-open-day',{detail:r.day})));row.append(open,el('p','achievement-text',r.text));weekly.append(row);}
    $('menu-plan').append(weekly);
  }
  async function refresh(detail){
    if(!detail)return;context=detail;const id=++sequence;
    try{const saved=await api('/achievements?start='+detail.week);if(id!==sequence)return;records=saved;render();}
    catch(e){if(id!==sequence)return;document.querySelectorAll('[data-diary-block]').forEach(n=>n.remove());const block=card('🌸 Дневник поощрений');block.dataset.diaryBlock='error';const err=el('p','error',e.message);err.setAttribute('role','alert');block.append(err,button('Попробовать ещё раз','text-button',()=>refresh(context)));$('menu-plan').append(block);}
  }
  window.addEventListener('menu-plan-render',event=>refresh(event.detail));
})();
