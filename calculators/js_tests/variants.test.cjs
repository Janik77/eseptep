// Exercise the shipped event handlers with a small DOM contract, without dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');

function node(dataset = {}, textContent = '') {
    const classes = new Set();
    return {dataset, textContent, value: '', handlers: {}, attributes: {},
        classList: {contains: x => classes.has(x), add: x => classes.add(x), remove: x => classes.delete(x),
            toggle: (x, enabled) => enabled ? classes.add(x) : classes.delete(x)},
        addEventListener(type, callback) {this.handlers[type] = callback;},
        setAttribute(name, value) {this.attributes[name] = value;},
    };
}

test('variant click updates summary, total, rows, hidden save inputs and copied text', async () => {
    for (const keys of [['economy', 'comfort', 'business'], ['base', 'optimal', 'maximum']]) {
        const label = node(), summary = node(), total = node(), copy = node(), toast = node();
        const hidden = [node(), node(), node()];
        const buttons = keys.map((key, i) => {
            const button = node({variantButton: key, variantCount: String(i + 2), variantTotal: String((i + 1) * 100)});
            button.querySelector = () => node({}, key);
            return button;
        });
        const panels = keys.map(key => node({variantPanel: key}));
        const sources = Object.fromEntries(keys.map(key => [key, {value: `Materials for ${key}`} ]));
        const card = {querySelector: selector => selector === '[data-summary-variant]' ? summary : total};
        const root = {
            closest: () => card,
            querySelectorAll: selector => selector === '[data-variant-button]' ? buttons : panels,
            querySelector: selector => ({'[data-active-variant-label]': label, '[data-copy-variant]': copy, '[data-variant-copy-toast]': toast}[selector] || sources[selector.match(/data-variant-copy-source="([^"]+)"/)?.[1]])
        };
        let copied;
        const context = {
            document: {documentElement: node(), addEventListener() {}, querySelectorAll: selector => selector === '[data-variant-result]' ? [root] : hidden},
            navigator: {clipboard: {async writeText(text) {copied = text;}}},
            window: {setTimeout() {}},
        };
        vm.createContext(context);
        vm.runInContext(fs.readFileSync('static/js/app.js', 'utf8'), context);
        context.initVariantResults();
        for (const [index, key] of keys.entries()) {
            buttons[index].handlers.click();
            assert.equal(label.textContent, key);
            assert.equal(summary.textContent, `${key} · ${index + 2} позиций · цены справочно`);
            assert.equal(total.textContent, `₸ ${(index + 1) * 100}`);
            panels.forEach((panel, i) => assert.equal(panel.classList.contains('is-active'), i === index));
            buttons.forEach((button, i) => assert.equal(button.attributes['aria-selected'], String(i === index)));
            hidden.forEach(input => assert.equal(input.value, key));
            await copy.handlers.click();
            assert.equal(copied, `Materials for ${key}`);
        }
    }
});
