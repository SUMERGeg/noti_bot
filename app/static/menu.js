'use strict';
(() => {
  const M=window.MenuCore, root=$('nutrition');
  const categories=['Завтраки','Основные блюда','Гарниры','Салаты','Супы','Десерты','Перекусы','Напитки','Другое'];
  const meals={breakfast:'Завтрак',lunch:'Обед',dinner:'Ужин',snack:'Перекусы'};
  const icons={breakfast:'☀',lunch:'◒',dinner:'☾',snack:'♡'};
  const state={date:M.today(),week:M.weekStart(M.today()),days:[],dishes:[],settings:{calorie_goal:null,theme:'light',decimals:1},tab:'plan',overview:false,search:'',category:'',favorites:false};
  let mounted=false, loaded=false, loading=false, requestId=0, panelId=0;
  const dialog=el('dialog'); dialog.id='menu-dialog'; dialog.setAttribute('aria-labelledby','menu-dialog-title'); document.body.append(dialog);
  const num=n=>new Intl.NumberFormat('ru',{maximumFractionDigits:state.settings.decimals}).format(n||0);
  const amountNum=n=>new Intl.NumberFormat('ru',{maximumFractionDigits:6}).format(n||0);
  const basisLabel=dish=>dish.nutrition_basis==='per_portion'?'1 порцию':'100 г';
  const amountLabel=entry=>entry.unit==='portions'?amountNum(entry.quantity)+' порц.'+(entry.grams!=null?' ('+amountNum(entry.grams)+' г)':''):amountNum(entry.quantity??entry.grams)+' г';
  const dateText=(s,options={day:'numeric',month:'long'})=>new Intl.DateTimeFormat('ru',options).format(M.parse(s));
  const button=(label,cls,fn)=>{const b=el('button',cls,label);b.type='button';if(fn)b.onclick=fn;return b;};
  const option=(value,label)=>{const o=el('option','',label);o.value=value;return o;};
  function store(key,value){try{localStorage.setItem(key,value);}catch{}}
  function applyTheme(theme){document.documentElement.dataset.theme=theme;store('menu-theme',theme);try{tg?.setHeaderColor(theme==='dark'?'#1b241e':'#f7f8f2');tg?.setBackgroundColor(theme==='dark'?'#1b241e':'#f7f8f2');}catch{}}
  try{applyTheme(localStorage.getItem('menu-theme')==='dark'?'dark':'light');}catch{}
  function errorText(error){return error?.message||'Не удалось выполнить действие. Попробуй ещё раз.';}
  async function run(fn,btn){if(btn)btn.disabled=true;try{await fn();}catch(e){notify(errorText(e));}finally{if(btn)btn.disabled=false;}}
  function field(label,input){const wrap=el('div','menu-field'),id='mf-'+Math.random().toString(36).slice(2);input.id=id;const l=el('label','',label);l.htmlFor=id;wrap.append(l,input);return wrap;}
  function input(type,value=''){const i=el('input');i.type=type;i.value=value;return i;}
  function number(value='',required=true){const i=input('number',value);i.step='any';i.min='0';i.required=required;return i;}
  function panel(title,body,onSave,label='Сохранить'){
    const version=++panelId,form=el('form','dialog-content'),head=el('div','dialog-head'),heading=el('div');
    heading.append(el('div','eyebrow','С ЗАБОТОЙ О ТЕБЕ ♡'));const h=el('h2','',title);h.id='menu-dialog-title';heading.append(h);
    head.append(heading,button('×','icon-button',()=>dialog.close()));head.lastChild.setAttribute('aria-label','Закрыть');
    const scroll=el('div','dialog-body');scroll.append(body);const error=el('p','error');error.hidden=true;error.setAttribute('role','alert');scroll.append(error);
    const footer=el('div','form-actions');footer.append(button(onSave?'Отмена':'Закрыть','button secondary',()=>dialog.close()));
    if(onSave){const save=button(label,'button primary');save.type='submit';footer.append(save);form.onsubmit=async e=>{e.preventDefault();save.disabled=true;error.hidden=true;try{await onSave();if(panelId===version)dialog.close();}catch(err){error.textContent=errorText(err);error.hidden=false;error.scrollIntoView({block:'nearest'});}finally{save.disabled=false;}};}
    form.append(head,scroll,footer);dialog.replaceChildren(form);if(!dialog.open)dialog.showModal();
  }
  function nutrition(values,cls='macro-grid'){
    const n=el('div',cls);for(const [key,label,unit] of [['calories','Калории','ккал'],['protein','Белки','г'],['fat','Жиры','г'],['carbs','Углеводы','г']]){
      const cell=el('div','macro '+key);cell.append(el('strong','',num(values[key])+' '+unit),el('span','',label));n.append(cell);
    }return n;
  }
  function mount(){
    root.innerHTML=`<div class="menu-heading"><div class="eyebrow">ВКУСНО, СПОКОЙНО, ПО-ТВОЕМУ</div><h1>Моё меню<span> ♡</span></h1><p>Муся, пусть забота будет и на тарелке.</p></div>
      <p id="menu-error" class="error" role="alert" hidden></p><button type="button" id="menu-retry" class="button secondary" hidden>Попробовать ещё раз</button><div id="menu-loading" class="skeleton" hidden></div>
      <div id="menu-content" hidden>
      <section id="menu-plan"><div class="week-toolbar"><button type="button" id="week-prev" class="icon-button" aria-label="Предыдущая неделя">‹</button><h2 id="menu-month"></h2><button type="button" id="week-next" class="icon-button" aria-label="Следующая неделя">›</button></div><div class="plan-tools"><button type="button" id="week-today" class="text-button">К текущей неделе</button><div class="segments"><button type="button" id="view-day" aria-pressed="true">День</button><button type="button" id="view-week" aria-pressed="false">Неделя</button></div></div><div id="menu-days" class="menu-days" aria-label="Дни недели"></div><div id="day-plan"></div><div class="plan-actions"><button type="button" id="copy-day" class="button secondary">Копировать день</button><button type="button" id="copy-week" class="button secondary">Повторить неделю</button><button type="button" id="clear-day" class="text-button danger-text">Очистить день</button></div></section>
      <section id="menu-catalog" hidden><div class="section-head"><h2>Мои блюда <span id="dish-count" class="pill"></span></h2><button type="button" id="new-dish" class="button primary compact">＋ Добавить блюдо</button></div><input type="search" id="dish-search" aria-label="Поиск блюд" placeholder="Найти что-нибудь вкусное…"><div class="catalog-filters"><select id="dish-category" aria-label="Категория блюд"><option value="">Все категории</option></select><button type="button" id="dish-favorites" class="button secondary" aria-pressed="false">♡ Избранное</button></div><p class="hint">По алфавиту · КБЖУ на 100 г или на порцию</p><div id="dish-list" class="dish-list"></div></section>
      <section id="menu-settings" hidden></section></div>
      <nav class="menu-nav" aria-label="Разделы рациона"><button type="button" data-menu-tab="plan" aria-pressed="true"><span>▦</span>План питания</button><button type="button" data-menu-tab="catalog" aria-pressed="false"><span>♧</span>Мои блюда</button><button type="button" data-menu-tab="settings" aria-pressed="false"><span>⚙</span>Настройки</button></nav>`;
    categories.forEach(c=>$('dish-category').append(option(c,c)));
    root.querySelectorAll('[data-menu-tab]').forEach(b=>b.onclick=()=>{state.tab=b.dataset.menuTab;render();});
    $('week-prev').onclick=()=>shift(-7);$('week-next').onclick=()=>shift(7);
    $('week-today').onclick=()=>{state.date=M.today();state.week=M.weekStart(state.date);run(loadPlan);};
    $('view-day').onclick=()=>{state.overview=false;renderPlan();};$('view-week').onclick=()=>{state.overview=true;renderPlan();};
    $('new-dish').onclick=()=>editDish();$('dish-search').oninput=e=>{state.search=e.target.value;renderCatalog();};
    $('dish-category').onchange=e=>{state.category=e.target.value;renderCatalog();};
    $('dish-favorites').onclick=()=>{state.favorites=!state.favorites;$('dish-favorites').setAttribute('aria-pressed',state.favorites);renderCatalog();};
    $('copy-day').onclick=()=>copyPanel('day');$('copy-week').onclick=()=>copyPanel('week');
    $('clear-day').onclick=()=>{if(confirm('Очистить меню на '+dateText(state.date)+'?'))run(async()=>{await api('/menu/day/'+state.date,{method:'DELETE'});await loadPlan();notify('Меню дня очищено');},$('clear-day'));};
    $('menu-retry').onclick=()=>ensure(true);mounted=true;
  }
  async function ensure(force=false){
    if(!mounted)mount();if(loading||loaded&&!force)return;
    loading=true;$('menu-loading').hidden=false;$('menu-error').hidden=true;$('menu-retry').hidden=true;
    try{const [dishes,settings,plan]=await Promise.all([api('/menu/dishes'),api('/menu/settings'),api('/menu/plan?start='+state.week)]);state.dishes=dishes;state.settings=settings;state.days=plan.days;loaded=true;applyTheme(settings.theme);render();}
    catch(e){$('menu-error').textContent=errorText(e);$('menu-error').hidden=false;$('menu-retry').hidden=false;}
    finally{loading=false;$('menu-loading').hidden=true;}
  }
  async function loadPlan(){const id=++requestId,week=state.week;const plan=await api('/menu/plan?start='+week);if(id===requestId&&state.week===week){state.days=plan.days;renderPlan();}}
  function shift(delta){state.date=M.addDays(state.date,delta);state.week=M.weekStart(state.date);run(loadPlan);}
  function render(){
    $('menu-content').hidden=!loaded;
    for(const tab of ['plan','catalog','settings'])$('menu-'+tab).hidden=state.tab!==tab;
    root.querySelectorAll('[data-menu-tab]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.menuTab===state.tab));
    if(state.tab==='plan')renderPlan();else if(state.tab==='catalog')renderCatalog();else renderSettings();
  }
  function renderPlan(){
    $('menu-month').textContent=dateText(state.date,{month:'long',year:'numeric'});$('menu-days').replaceChildren();
    for(let i=0;i<7;i++){const date=M.addDays(state.week,i),b=button('','day-button',()=>{state.date=date;renderPlan();});b.setAttribute('aria-label',dateText(date,{weekday:'long',day:'numeric',month:'long'}));b.setAttribute('aria-pressed',date===state.date);if(date===M.today())b.classList.add('today');b.append(el('span','',['Пн','Вт','Ср','Чт','Пт','Сб','Вс'][i]),el('strong','',M.parse(date).getDate()));$('menu-days').append(b);}
    $('view-day').setAttribute('aria-pressed',!state.overview);$('view-week').setAttribute('aria-pressed',state.overview);
    const out=$('day-plan');out.replaceChildren();
    if(state.overview){for(const day of state.days){const card=button('','week-card',()=>{state.date=day.day;state.overview=false;renderPlan();});card.append(el('h3','',dateText(day.day,{weekday:'long',day:'numeric',month:'short'})));for(const [key,label] of Object.entries(meals)){const items=day.meals[key].entries;card.append(el('p','',label+': '+(items.length?items.map(e=>e.title+' · '+amountLabel(e)).join('; '):'—')));}card.append(el('strong','',num(day.totals.calories)+' ккал'));out.append(card);}return;}
    const day=state.days.find(d=>d.day===state.date);if(!day)return;
    const total=el('section','day-total');total.append(el('div','eyebrow','ИТОГО ЗА ДЕНЬ'),nutrition(day.totals));
    if(state.settings.calorie_goal)total.append(el('p','goal-note',num(day.totals.calories)+' / '+num(state.settings.calorie_goal)+' ккал · твой ориентир'));
    out.append(total);
    for(const [key,label] of Object.entries(meals)){
      const meal=day.meals[key],card=el('section','meal-card'),head=el('div','section-head');head.append(el('h3','',icons[key]+' '+label),button('＋ Добавить','text-button',()=>picker(key)));card.append(head);
      if(!meal.entries.length)card.append(el('p','meal-empty','Пока ничего не запланировано'));
      for(const entry of meal.entries){const row=el('div','meal-entry'),info=el('div','entry-info');info.append(el('strong','',entry.title),el('p','',amountLabel(entry)+' · '+num(entry.nutrition.calories)+' ккал'));
        const details=el('details','entry-macros');details.append(el('summary','','БЖУ'),el('p','','Белки '+num(entry.nutrition.protein)+' г · Жиры '+num(entry.nutrition.fat)+' г · Углеводы '+num(entry.nutrition.carbs)+' г'));info.append(details);
        const actions=el('div','entry-actions'),edit=button('✎','icon-button',()=>portionPanel(entry,key,true)),remove=button('×','icon-button',()=>run(async()=>{await api('/menu/entries/'+entry.id,{method:'DELETE'});await loadPlan();},remove));
        edit.setAttribute('aria-label','Изменить порцию '+entry.title);remove.setAttribute('aria-label','Убрать из меню '+entry.title);actions.append(edit,remove);row.append(info,actions);card.append(row);
      }
      const bottom=el('div','meal-bottom');bottom.append(el('span','',num(meal.totals.calories)+' ккал'),button('Копировать','text-button',()=>copyPanel('meal',key)));card.append(bottom);out.append(card);
    }
  }
  function filtered(list,search,category,favorites){return list.filter(d=>(!search||d.title.toLocaleLowerCase('ru').includes(search.toLocaleLowerCase('ru')))&&(!category||d.category===category)&&(!favorites||d.favorite)).sort((a,b)=>a.title.localeCompare(b.title,'ru'));}
  function renderCatalog(){
    const list=$('dish-list');list.replaceChildren();$('dish-count').textContent=state.dishes.length;
    const dishes=filtered(state.dishes,state.search,state.category,state.favorites);
    if(!dishes.length){list.append(el('div','empty',state.dishes.length?'Ничего не нашлось. Попробуй другой поиск ♡':'Здесь будут твои любимые блюда, Муся ♡'));return;}
    for(const dish of dishes){const card=el('article','dish-card'),open=button('','dish-open',()=>viewDish(dish));
      if(dish.photo){const img=el('img','dish-thumb');img.src=dish.photo;img.alt='';img.loading='lazy';open.append(img);}else open.append(el('span','dish-emoji','♧'));
      const info=el('div');info.append(el('strong','',dish.title),el('span','',dish.category),el('p','',num(dish.calories)+' ккал / '+basisLabel(dish)));open.append(info);
      const favorite=button(dish.favorite?'♥':'♡','favorite-button',()=>run(async()=>{const saved=await api('/menu/dishes/'+dish.id,{method:'PUT',body:JSON.stringify({...dish,favorite:!dish.favorite})});state.dishes=state.dishes.map(d=>d.id===saved.id?saved:d);renderCatalog();},favorite));favorite.setAttribute('aria-label',(dish.favorite?'Убрать из избранного ':'В избранное ')+dish.title);favorite.setAttribute('aria-pressed',dish.favorite);card.append(open,favorite);list.append(card);
    }
  }
  function viewDish(dish){
    const body=el('div');if(dish.photo){const img=el('img','dish-photo');img.src=dish.photo;img.alt=dish.title;body.append(img);}
    body.append(el('p','hint',dish.category+' · КБЖУ на '+basisLabel(dish)),nutrition(dish));
    if(dish.portion_weight)body.append(el('p','hint','Одна порция — '+amountNum(dish.portion_weight)+' г'));
    if(dish.note)body.append(el('p','reading',dish.note));if(dish.recipe_url){const link=el('a','recipe-link','Открыть рецепт ↗');link.href=dish.recipe_url;link.target='_blank';link.rel='noopener noreferrer';body.append(link);}
    const remove=button('Удалить блюдо','button danger',()=>{if(confirm('Удалить «'+dish.title+'» из каталога? Составленное меню сохранится.'))run(async()=>{await api('/menu/dishes/'+dish.id,{method:'DELETE'});state.dishes=state.dishes.filter(d=>d.id!==dish.id);renderCatalog();dialog.close();},remove);});body.append(el('p','hint','Изменение блюда не меняет уже составленное меню.'),remove);
    panel(dish.title,body,async()=>editDish(dish),'Редактировать');
  }
  async function compressPhoto(file){
    if(!['image/jpeg','image/png','image/webp'].includes(file.type))throw new Error('Выбери фотографию JPG, PNG или WebP.');
    if(file.size>20*1024*1024)throw new Error('Выбери фотографию меньше 20 МБ.');
    const image=await createImageBitmap(file);try{const canvas=document.createElement('canvas'),scale=Math.min(1,900/Math.max(image.width,image.height));canvas.width=Math.max(1,Math.round(image.width*scale));canvas.height=Math.max(1,Math.round(image.height*scale));const ctx=canvas.getContext('2d');ctx.fillStyle='#ffffff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(image,0,0,canvas.width,canvas.height);const data=canvas.toDataURL('image/jpeg',.65);if(data.length>700000)throw new Error('Фото получилось слишком большим. Выбери другое.');return data;}finally{image.close();}
  }
  function editDish(dish=null){
    const body=el('div'),title=input('text',dish?.title||'');title.required=true;title.maxLength=200;title.placeholder='Например, лазанья с индейкой';
    const category=el('select');categories.forEach(c=>category.append(option(c,c)));category.value=dish?.category||'Основные блюда';
    const basis=el('select');basis.append(option('per100g','На 100 г'),option('per_portion','На одну порцию'));basis.value=dish?.nutrition_basis||'per100g';
    const basisHint=el('p','hint');const updateBasisHint=()=>{basisHint.textContent=(basis.value==='per_portion'?'Введи КБЖУ одной целой порции.':'Введи КБЖУ на 100 г готового блюда.')+' При смене способа проверь, что значения соответствуют выбранной основе.';};basis.onchange=updateBasisHint;updateBasisHint();
    const weight=number(dish?.portion_weight??'',false);weight.min='0.001';weight.max='100000';weight.placeholder='Например, 250 · можно не заполнять';
    body.append(field('Название блюда *',title),field('Категория *',category),field('Как указать КБЖУ',basis),basisHint);
    const macros=el('div','dish-fields'),fields={};for(const [key,label] of [['calories','Калории, ккал *'],['protein','Белки, г *'],['fat','Жиры, г *'],['carbs','Углеводы, г *']]){fields[key]=number(dish?.[key]??'');fields[key].max=key==='calories'?'100000':'1000';macros.append(field(label,fields[key]));}body.append(macros);
    body.append(field('Вес одной порции, г · необязательно',weight),el('p','hint','Вес нужен для пересчёта между граммами и порциями. Если он неизвестен, можно считать в единицах выбранной основы.'));
    let photo=dish?.photo||'',photoPending=false;const image=el('img','dish-photo');image.hidden=!photo;if(photo)image.src=photo;
    const upload=input('file');upload.accept='image/jpeg,image/png,image/webp';const status=el('p','hint');status.setAttribute('role','status');
    upload.onchange=async()=>{if(!upload.files[0])return;photoPending=true;status.textContent='Уменьшаю фотографию…';try{photo=await compressPhoto(upload.files[0]);image.src=photo;image.hidden=false;status.textContent='Фотография готова ♡';}catch(e){status.textContent=errorText(e);}finally{photoPending=false;upload.value='';}};
    const removePhoto=button('Убрать фото','text-button',()=>{photo='';image.removeAttribute('src');image.hidden=true;status.textContent='';});
    const note=el('textarea');note.rows=3;note.maxLength=20000;note.value=dish?.note||'';const link=input('url',dish?.recipe_url||'');link.placeholder='https://…';link.maxLength=2000;
    body.append(field('Фотография · необязательно',upload),status,image,removePhoto,field('Описание или заметка',note),field('Ссылка на рецепт',link));
    panel(dish?'Редактировать блюдо':'Новое блюдо',body,async()=>{if(photoPending)throw new Error('Подожди, фотография ещё обрабатывается.');const data={title:title.value.trim(),category:category.value,note:note.value,recipe_url:link.value.trim(),photo,favorite:dish?.favorite||false,nutrition_basis:basis.value,portion_weight:weight.value===''?null:Number(weight.value)};for(const key of Object.keys(fields))data[key]=Number(fields[key].value);const saved=await api('/menu/dishes'+(dish?'/'+dish.id:''),{method:dish?'PUT':'POST',body:JSON.stringify(data)});state.dishes=state.dishes.filter(d=>d.id!==saved.id);state.dishes.push(saved);if(state.tab==='catalog')renderCatalog();notify('Вкусное сохранено, Муся ♡');},'Сохранить блюдо');
  }
  function picker(meal){
    const body=el('div'),search=input('search'),select=el('select'),list=el('div','picker-list');search.placeholder='Поиск блюда';search.setAttribute('aria-label','Поиск блюда');select.setAttribute('aria-label','Категория блюда');select.append(option('','Все категории'));categories.forEach(c=>select.append(option(c,c)));body.append(search,select,list);
    const draw=()=>{list.replaceChildren();const dishes=filtered(state.dishes,search.value,select.value,false);if(!dishes.length)list.append(el('p','hint',state.dishes.length?'Ничего не найдено':'Сначала добавь блюдо в разделе «Мои блюда» ♡'));for(const dish of dishes){const b=button('','picker-dish',()=>portionPanel(dish,meal));b.append(el('strong','',dish.title),el('span','',num(dish.calories)+' ккал / '+basisLabel(dish)+' · '+dish.category));list.append(b);}};search.oninput=select.onchange=draw;draw();panel(meals[meal]+' · выбрать блюдо',body,null);
  }
  function portionPanel(dish,meal,isEntry=false){
    const day=state.date,body=el('div'),unit=el('select');
    for(const [value,label] of [['grams','В граммах'],['portions','В порциях']]){const o=option(value,label);o.disabled=!M.canMeasure(dish,value);unit.append(o);}
    unit.value=isEntry?(dish.unit||'grams'):(dish.nutrition_basis==='per_portion'?'portions':'grams');
    let previousUnit=unit.value;
    const quantity=number(isEntry?(dish.quantity??dish.grams):(unit.value==='portions'?1:250));quantity.min='0.001';quantity.max='100000';
    const quantityField=field('',quantity);
    body.append(el('p','hint',num(dish.calories)+' ккал / '+basisLabel(dish)+' · '+dateText(day)),field('Указать количество',unit),quantityField);
    body.append(el('p','hint',dish.portion_weight?'Одна порция — '+amountNum(dish.portion_weight)+' г':'Чтобы выбирать и граммы, и порции, добавь вес одной порции в настройках блюда.'));
    const slot=el('select');Object.entries(meals).forEach(([value,label])=>slot.append(option(value,label)));slot.value=meal;body.append(field('Приём пищи',slot));
    const preview=el('div');body.append(preview);const draw=()=>{quantityField.querySelector('label').textContent=unit.value==='portions'?'Количество порций *':'Масса, г *';preview.replaceChildren(nutrition(M.portion(dish,Math.max(0,Number(quantity.value)||0),unit.value)));};quantity.oninput=draw;
    unit.onchange=()=>{quantity.value=Number(M.convertQuantity(dish,Number(quantity.value)||0,previousUnit,unit.value).toFixed(6));previousUnit=unit.value;draw();};draw();
    panel(dish.title,body,async()=>{const data={quantity:Number(quantity.value),unit:unit.value,meal:slot.value};await api('/menu/entries'+(isEntry?'/'+dish.id:''),{method:isEntry?'PATCH':'POST',body:JSON.stringify(isEntry?data:{...data,day,dish_id:dish.id})});await loadPlan();notify(isEntry?'Порция обновлена':'Добавлено в твоё меню ♡');},isEntry?'Сохранить порцию':'Добавить в меню');
  }
  function copyPanel(scope,meal='breakfast'){
    const source=scope==='week'?state.week:state.date,body=el('div'),target=input('date',M.addDays(source,scope==='week'?7:1));target.required=true;
    body.append(el('p','hint',scope==='week'?'Вся текущая неделя будет скопирована на следующую.':'Копируем '+(scope==='meal'?meals[meal].toLowerCase():'меню дня')+' за '+dateText(source)+'.'));
    if(scope!=='week')body.append(field('На какую дату',target));const slot=el('select');Object.entries(meals).forEach(([k,l])=>slot.append(option(k,l)));slot.value=meal;if(scope==='meal')body.append(field('В какой приём пищи',slot));
    body.append(el('p','copy-warning','Меню '+(scope==='meal'?'выбранного приёма пищи':scope==='week'?'следующей недели':'выбранного дня')+' будет заменено. Остальные даты сохранятся.'));
    panel(scope==='week'?'Повторить неделю':scope==='meal'?'Копировать приём пищи':'Копировать день',body,async()=>{const r=await api('/menu/copy',{method:'POST',body:JSON.stringify({source,target:target.value,scope,source_meal:meal,target_meal:slot.value})});await loadPlan();notify('Скопировано порций: '+r.copied);},'Заменить и скопировать');
  }
  function renderSettings(){
    const out=$('menu-settings');out.replaceChildren(el('h2','','Настройки'));const form=el('form','settings-card'),goal=number(state.settings.calorie_goal??'',false);goal.min='1';goal.placeholder='Можно оставить пустым';
    const theme=el('select');theme.append(option('light','Светлая'),option('dark','Тёмная'));theme.value=state.settings.theme;
    const decimals=el('select');[0,1,2].forEach(n=>decimals.append(option(String(n),n===0?'Целые числа':n===1?'До 1 знака после запятой':'До 2 знаков после запятой')));decimals.value=state.settings.decimals;
    form.append(field('Дневной ориентир, ккал',goal),el('p','hint','Только ориентир, Муся. Здесь нет оценок и ограничений ♡'),field('Тема приложения',theme),field('Отображение чисел',decimals));const error=el('p','error');error.hidden=true;error.setAttribute('role','alert');const save=button('Сохранить настройки','button primary');save.type='submit';form.append(error,save);
    form.onsubmit=async e=>{e.preventDefault();save.disabled=true;error.hidden=true;try{state.settings=await api('/menu/settings',{method:'PUT',body:JSON.stringify({calorie_goal:goal.value===''?null:Number(goal.value),theme:theme.value,decimals:Number(decimals.value)})});applyTheme(state.settings.theme);notify('Всё по-твоему, Муся ♡');}catch(err){error.textContent=errorText(err);error.hidden=false;}finally{save.disabled=false;}};out.append(form);
  }
  function switchMain(menu){$('reminders-view').hidden=menu;root.hidden=!menu;$('show-reminders').setAttribute('aria-pressed',!menu);$('show-menu').setAttribute('aria-pressed',menu);document.body.classList.toggle('nutrition-active',menu);if(menu)ensure();}
  $('show-reminders').onclick=()=>switchMain(false);$('show-menu').onclick=()=>switchMain(true);
  // Apply saved server settings even when opening a notification card first.
  api('/menu/settings').then(settings=>{state.settings=settings;applyTheme(settings.theme);}).catch(()=>{});
})();
