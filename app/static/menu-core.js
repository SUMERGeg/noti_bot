'use strict';
(() => {
  const keys = ['calories','protein','fat','carbs'];
  const parse = s => { const [y,m,d] = s.split('-').map(Number); return new Date(y,m-1,d,12); };
  const iso = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  const addDays = (s,n) => {const d=parse(s); d.setDate(d.getDate()+n); return iso(d);};
  const canMeasure = (dish, unit) => unit === (dish.nutrition_basis === 'per_portion' ? 'portions' : 'grams') || Number(dish.portion_weight) > 0;
  const convertQuantity = (dish, quantity, from, to) => {
    if(from===to)return quantity;
    if(!(Number(dish.portion_weight)>0))throw new Error('Укажи вес одной порции для пересчёта.');
    return from==='grams'?quantity/dish.portion_weight:quantity*dish.portion_weight;
  };
  const portion = (dish, quantity, unit='grams') => {
    if(!canMeasure(dish,unit))throw new Error('Укажи вес одной порции для пересчёта.');
    const perPortion=dish.nutrition_basis==='per_portion';
    const factor=perPortion?(unit==='portions'?quantity:quantity/dish.portion_weight):(unit==='grams'?quantity/100:quantity*dish.portion_weight/100);
    return Object.fromEntries(keys.map(k => [k,Number(dish[k])*factor]));
  };
  const core = {
    parse, iso, addDays,
    today: () => iso(new Date()),
    weekStart: s => addDays(s, -(parse(s).getDay()+6)%7),
    portion, canMeasure, convertQuantity,
    total: list => Object.fromEntries(keys.map(k => [k,list.reduce((sum,n)=>sum+Number(n[k]||0),0)])),
  };
  if (typeof module !== 'undefined' && module.exports) module.exports=core;
  else window.MenuCore=core;
})();
