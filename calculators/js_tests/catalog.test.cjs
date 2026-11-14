const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../static/js/catalog.js'), 'utf8');
function element(extra = {}) {
  return { hidden: false, events: {}, attrs: {}, classList: { toggle() {} },
    addEventListener(event, fn) { this.events[event] = fn; },
    setAttribute(k, v) { this.attrs[k] = v; }, focus() { this.focused = true; }, ...extra };
}
function setup() {
  const cards = [element({dataset:{group:'prepare'},textContent:'Демонтаж'}), element({dataset:{group:'finish'},textContent:'Плитка Керамогранит'}), element({dataset:{group:'systems'},textContent:'Тёплый пол'})];
  const filters = ['all','prepare','systems','finish'].map(filter => element({dataset:{filter}}));
  const search = element({value:''}), empty = element(), count = element(), reset = element();
  const toolbar = element({hidden:true,querySelectorAll:()=>filters,querySelector:()=>search});
  const nodes = {'[data-catalog-toolbar]':toolbar, '[data-catalog-empty]':empty, '[data-catalog-count]':count,'[data-catalog-reset]':reset};
  vm.runInNewContext(source, {document:{querySelector:selector=>nodes[selector],querySelectorAll:()=>cards}});
  return {cards,filters,search,empty,count,reset,toolbar};
}
test('catalog remains usable and reveals enhancement only after initialization',()=>{const x=setup();assert.equal(x.toolbar.hidden,false);assert.equal(x.cards.filter(c=>!c.hidden).length,3);assert.equal(x.empty.hidden,true);});
test('filters and search compose; reset restores links and keyboard focus',()=>{const x=setup();x.filters[3].events.click();assert.deepEqual(x.cards.map(c=>c.hidden),[true,false,true]);assert.equal(x.filters[3].attrs['aria-pressed'],'true');x.search.value='нет такого';x.search.events.input();assert.equal(x.empty.hidden,false);assert.equal(x.count.textContent,'Показано: 0 из 3');x.reset.events.click();assert.equal(x.search.focused,true);assert.equal(x.search.value,'');assert.ok(x.cards.every(c=>!c.hidden));});
test('Russian case, ё and whitespace normalize without changing content',()=>{const x=setup();x.search.value=' ТЕПЛЫЙ ';x.search.events.input();assert.deepEqual(x.cards.map(c=>c.hidden),[true,true,false]);});
test('script is harmless on other pages',()=>{vm.runInNewContext(source,{document:{querySelector:()=>null}});});
