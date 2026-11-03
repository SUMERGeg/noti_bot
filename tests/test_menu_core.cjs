const {test} = require('node:test');
const assert = require('node:assert/strict');
const M = require('../app/static/menu-core.js');
test('250 g portion uses all four values and accepts fractional grams', () => {
  assert.deepEqual(M.portion({calories:200,protein:15,fat:9,carbs:14},250), {calories:500,protein:37.5,fat:22.5,carbs:35});
  assert.equal(M.portion({calories:200,protein:0,fat:0,carbs:0},180).calories,360);
});
test('sums unrounded portions, including an empty day', () => {
  assert.equal(M.total([{calories:.14,protein:0,fat:0,carbs:0},{calories:.14,protein:0,fat:0,carbs:0}]).calories,.28);
  assert.deepEqual(M.total([]),{calories:0,protein:0,fat:0,carbs:0});
});
test('calendar handles year and month boundaries without UTC shifts', () => {
  assert.equal(M.weekStart('2027-01-01'),'2026-12-28');
  assert.equal(M.addDays('2026-12-28',7),'2027-01-04');
  assert.equal(M.addDays('2028-02-28',1),'2028-02-29');
});
test('fractional portions with or without a declared weight',()=>{
  const dish={calories:500,protein:30,fat:20,carbs:50,nutrition_basis:'per_portion'};
  assert.deepEqual(M.portion(dish,1.5,'portions'),{calories:750,protein:45,fat:30,carbs:75});
  assert.equal(M.portion({...dish,portion_weight:250},180,'grams').calories,360);
  assert.throws(()=>M.portion(dish,100,'grams'));
});
test('100g nutrition supports portions when their weight is known',()=>{
  const dish={calories:200,protein:0,fat:0,carbs:0,portion_weight:250};
  assert.equal(M.portion(dish,1.5,'portions').calories,750);
  assert.equal(M.convertQuantity(dish,1.5,'portions','grams'),375);
  assert.equal(M.convertQuantity(dish,375,'grams','portions'),1.5);
  assert.throws(()=>M.portion({...dish,portion_weight:null},1,'portions'));
});
