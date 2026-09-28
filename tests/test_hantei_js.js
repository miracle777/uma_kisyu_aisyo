// Node.js標準機能のみで既存の色分けとnullガードを検証する。
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const code = fs.readFileSync(path.join(__dirname, '../static/js/hantei.js'), 'utf8');
function run(table) {
  const context = { document: { getElementById: id => id === 'kanteitable' ? table : null } };
  vm.createContext(context); vm.runInContext(code, context); context.hantei();
}
run(null);
console.log('PASS 1: 表がない入力ページで例外にならない');
const cells = ['1','2','3'].map(innerText => ({id:'chk',innerText,style:{}}));
run({rows:[{cells}]});
assert.deepEqual(cells.map(c=>c.style.backgroundColor),['#FF0000','#FF7F00','#ffffff']);
console.log('PASS 2: 既存の赤・橙・白の色分けを維持');
const ignored={id:'other',innerText:'1',style:{}};
run({rows:[{cells:[ignored]}]});
assert.deepEqual(ignored.style,{});
console.log('PASS 3: 判定セル以外は変更しない');
