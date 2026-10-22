/* Exercise the actual browser script with a small DOM adapter, no packages. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function mount(search = '') {
  const records = [
    {search:'history 日本 京都 museum',subjects:['History']},
    {search:'arts 日本 museum',subjects:['Arts']},
    {search:'history london library',subjects:['History']},
  ];
  function element(value='') { return {value,hidden:false,disabled:false,textContent:'',events:{},addEventListener(k,f){this.events[k]=f;},focus(){},scrollIntoView(){}}; }
  const ids = Object.fromEntries(['search-data','search-form','q','pagination','count','empty','previous','next','page-status','reset','results-title'].map(k=>[k,element()]));
  ids['search-data'].textContent=JSON.stringify({records,pageSize:1,words:{found:'{visible} of {total}',page:'{page}/{pages}'}});
  const select=element(); select.name='subjects';
  ids['search-form'].querySelectorAll=()=>[select];
  ids['search-form'].reset=()=>{ids.q.value='';select.value='';};
  const cards=records.map(()=>element());
  const location={href:'https://example.test/repo/index.html'+search,search};
  const window={events:{},addEventListener(k,f){this.events[k]=f;}};
  const history={};
  for(const k of ['pushState','replaceState']) history[k]=(a,b,url)=>{location.href=url.href;location.search=url.search;};
  const document={getElementById:k=>ids[k],querySelectorAll:s=>s==='[data-index]'?cards:[]};
  vm.runInNewContext(fs.readFileSync('assets/search.js','utf8'),{document,window,location,history,URL,URLSearchParams,setTimeout,clearTimeout});
  return {ids,select,cards,location,window};
}
test('Japanese AND search works from a shareable subpath URL',()=>{
  const m=mount('?q=history+%E6%97%A5%E6%9C%AC');
  assert.equal(m.ids.count.textContent,'1 of 3');
  assert.deepEqual(m.cards.map(c=>c.hidden),[false,true,true]);
});
test('width and case normalization match',()=>{
  const m=mount('?q=ＨＩＳＴＯＲＹ');
  assert.equal(m.ids.count.textContent,'2 of 3');
});
test('keyword and subject filters combine',()=>{
  const m=mount('?q=museum&subjects=Arts');
  assert.deepEqual(m.cards.map(c=>c.hidden),[true,false,true]);
});
test('empty results and reset recover the collection',()=>{
  const m=mount('?q=not-present');
  assert.equal(m.ids.empty.hidden,false);
  m.ids.reset.events.click();
  assert.equal(m.ids.count.textContent,'3 of 3');
  assert.equal(m.location.search,'');
});
test('pagination shows only the selected page and clamps large pages',()=>{
  const m=mount('?page=999');
  assert.equal(m.ids['page-status'].textContent,'3/3');
  assert.deepEqual(m.cards.map(c=>c.hidden),[true,true,false]);
  m.ids.previous.events.click();
  assert.deepEqual(m.cards.map(c=>c.hidden),[true,false,true]);
});
test('popstate restores URL query and selection',()=>{
  const m=mount();
  m.location.search='?q=library';
  m.location.href='https://example.test/repo/index.html?q=library';
  m.window.events.popstate();
  assert.equal(m.ids.q.value,'library');
  assert.deepEqual(m.cards.map(c=>c.hidden),[true,true,false]);
});
