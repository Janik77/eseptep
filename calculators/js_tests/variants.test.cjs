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
            const button = node({variantButton: key, variantCount: String(i + 2), variantTotal: String(593060 + i)});
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
            document: {documentElement: {...node(), lang: 'kk'}, addEventListener() {}, querySelectorAll: selector => selector === '[data-variant-result]' ? [root] : hidden},
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
            assert.equal(total.textContent, `593 0${60 + index} ₸`);
            panels.forEach((panel, i) => assert.equal(panel.classList.contains('is-active'), i === index));
            buttons.forEach((button, i) => assert.equal(button.attributes['aria-selected'], String(i === index)));
            hidden.forEach(input => assert.equal(input.value, key));
            await copy.handlers.click();
            assert.equal(copied, `Materials for ${key}`);
        }
    }
});

function copyContext({clipboard, execResult = true, execThrows = false} = {}) {
    const calls = {selected: false, removed: false, focusRestored: false, appended: false};
    const temporary = {
        style: {}, value: '', setAttribute() {}, focus() {},
        select() {calls.selected = true;},
        setSelectionRange(start, end) {calls.range = [start, end];},
        remove() {calls.removed = true;},
    };
    const context = {
        document: {
            documentElement: {...node(), lang: 'kk'}, addEventListener() {},
            activeElement: {focus() {calls.focusRestored = true;}},
            createElement(tag) {assert.equal(tag, 'textarea'); return temporary;},
            body: {appendChild(element) {assert.equal(element, temporary); calls.appended = true;}},
            execCommand(command) {
                assert.equal(command, 'copy');
                assert.equal(calls.appended, true);
                assert.equal(calls.selected, true);
                if (execThrows) throw new Error('Copy denied');
                return execResult;
            },
        },
        navigator: {clipboard},
        window: {setTimeout() {return 4;}, clearTimeout() {}},
    };
    vm.createContext(context);
    vm.runInContext(fs.readFileSync('static/js/app.js', 'utf8'), context);
    return {context, calls, temporary};
}

test('clipboard success avoids legacy copy', async () => {
    let copied;
    const {context, calls} = copyContext({clipboard: {async writeText(text) {copied = text;}}});
    assert.equal(await context.copyPlainText('Плитка — 24 м²'), true);
    assert.equal(copied, 'Плитка — 24 м²');
    assert.equal(calls.appended, false);
});

test('clipboard rejection falls back to a temporary selected textarea and restores focus', async () => {
    const {context, calls, temporary} = copyContext({clipboard: {async writeText() {throw new Error('Permission denied');}}});
    assert.equal(await context.copyPlainText('Плитка — 24 м²'), true);
    assert.equal(temporary.value, 'Плитка — 24 м²');
    assert.deepEqual(calls.range, [0, 'Плитка — 24 м²'.length]);
    assert.equal(calls.removed, true);
    assert.equal(calls.focusRestored, true);
});

test('copy failure never claims success, remains visible, and successful retry clears it', async () => {
    for (const execThrows of [false, true]) {
        const {context, calls} = copyContext({execResult: false, execThrows});
        const copied = await context.copyPlainText('Плитка');
        assert.equal(copied, false);
        assert.equal(calls.removed, true);
        assert.equal(calls.focusRestored, true);
        const button = node(), toast = node();
        context.showCopyFeedback(button, toast, copied, 'Скопировать');
        assert.equal(button.classList.contains('is-copied'), false);
        assert.match(button.textContent, /Не удалось/);
        assert.match(toast.textContent, /Копирование недоступно/);
        assert.equal(toast.classList.contains('is-visible'), true);
        assert.equal(button.copyFeedbackTimer, undefined);
        context.showCopyFeedback(button, toast, true, 'Скопировать');
        assert.equal(button.textContent, 'Скопировано');
        assert.equal(toast.textContent, 'Список скопирован');
    }
});

test('result flow respects reduced motion when scrolling to the result', () => {
    for (const reduce of [true, false]) {
        let behavior;
        const card = {scrollIntoView(options) {behavior = options.behavior;}};
        const context = {
            document: {documentElement: {...node(), lang: 'kk'}, addEventListener() {}, querySelectorAll: () => [],
                querySelector: selector => selector === '#estimate-result' ? card : selector === '[data-result-ready]' ? {} : null},
            window: {setTimeout(callback) {callback();}},
        };
        vm.createContext(context);
        vm.runInContext(fs.readFileSync('static/js/app.js', 'utf8'), context);
        context.initResultFlow(reduce);
        assert.equal(behavior, reduce ? 'auto' : 'smooth');
    }
    assert.match(fs.readFileSync('static/js/app.js', 'utf8'), /initResultFlow\(prefersReducedMotion\);/);
});
