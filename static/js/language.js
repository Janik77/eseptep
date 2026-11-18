/* Language changes are POSTed only to Django set_language, never to a business form. */
(() => {
  const t = (text) => typeof gettext === 'function' ? gettext(text) : text;
  const key = 'eseptep-language-draft:' + location.pathname;
  const fields = () => [...document.querySelectorAll('form:not([data-language-form]) input, form:not([data-language-form]) select, form:not([data-language-form]) textarea, [data-row-qty]')];
  const eligible = (el) => (el.name || el.hasAttribute('data-row-qty')) && !['password','file','submit','button','hidden'].includes(el.type) && !el.autocomplete?.includes('password');
  try {
    const saved = JSON.parse(sessionStorage.getItem(key) || 'null');
    sessionStorage.removeItem(key);
    if (saved && Date.now() - saved.time < 60000) {
      if (saved.masterTab) {
        const tab = document.getElementById(saved.masterTab);
        if (tab) tab.checked = true;
      }
      fields().filter(eligible).forEach((el, index) => {
        const old = saved.fields[index];
        if (!old || old.name !== el.name || old.type !== el.type) return;
        el.value = old.value;
        if (['checkbox','radio'].includes(el.type)) el.checked = old.checked;
        el.dispatchEvent(new Event('change', {bubbles:true}));
      });
    }
  } catch (_) { /* Browsers may disable storage; never lose the current form silently. */ }
  let busy = false;
  document.querySelectorAll('[data-language-form]').forEach(form => form.addEventListener('submit', async (event) => {
    const all = fields();
    const sensitive = all.some(el => (el.type === 'password' && el.value) || (el.type === 'file' && el.files?.length));
    const calc = document.querySelector('[data-calc-form], [data-preview-form]');
    const next = new URL(location.href);
    if (calc) {
      next.search = '';
      next.searchParams.set('_preview', (document.querySelector('[data-result-ready]') || calc.querySelector('[role=alert]')) ? '1' : '0');
      new FormData(calc).forEach((value, name) => {
        if (!['csrfmiddlewaretoken','action','project_id'].includes(name) && typeof value === 'string') next.searchParams.set(name, value);
      });
      const variant = document.querySelector('[data-selected-variant-input]')?.value
        || document.querySelector('[data-variant-button].is-active')?.dataset.variantButton;
      if (variant) next.searchParams.set('selected_variant', variant);
    }
    const selectedProject = document.querySelector('select[name=project_id]');
    if (selectedProject?.value) next.searchParams.set('project_id', selectedProject.value);
    const upload = document.querySelector('[name=upload_id]');
    if (upload?.value) next.searchParams.set('upload_id', upload.value);
    if (sensitive) {
      event.preventDefault();
      if (busy) return;
      busy = true;
      const submit = new FormData(form);
      submit.set('language', event.submitter.value);
      submit.set('next', next.pathname + next.search + next.hash);
      try {
        // Only language + CSRF + next go to set_language. Never send the business form.
        const response = await fetch(form.action, {method: 'POST', body: submit, credentials: 'same-origin'});
        if (!response.ok || new URL(response.url).origin !== location.origin) throw new Error('Language response unavailable');
        const page = new DOMParser().parseFromString(await response.text(), 'text/html');
        if (!page.querySelector('[data-language-form]') || !page.querySelector('main')) throw new Error('Invalid language page');
        const fresh = [...page.querySelectorAll('form:not([data-language-form]) input, form:not([data-language-form]) select, form:not([data-language-form]) textarea, [data-row-qty]')];
        if (all.some((old,index) => ['password','file'].includes(old.type) && (!fresh[index] || fresh[index].name !== old.name || fresh[index].type !== old.type))) throw new Error('Form changed');
        all.forEach((old, index) => {
          const replacement = fresh[index];
          if (!replacement || old.name !== replacement.name || old.type !== replacement.type || old.type === 'hidden') return;
          if (['password','file'].includes(old.type)) {
            // Reuse the actual node: FileList/password remain only in the live DOM.
            old.className = replacement.className;
            if (replacement.hasAttribute('aria-label')) old.setAttribute('aria-label', replacement.getAttribute('aria-label'));
            replacement.replaceWith(old);
          } else {
            replacement.value = old.value;
            if (['checkbox','radio'].includes(old.type)) replacement.checked = old.checked;
          }
        });
        document.documentElement.lang = page.documentElement.lang;
        document.title = page.title;
        document.body.replaceWith(page.body);
        const catalogue = document.createElement('script');
        catalogue.src = '/jsi18n/?language-refresh=' + Date.now();
        catalogue.onload = () => {
          const languageScript = document.createElement('script');
          languageScript.src = '/static/js/language.js';
          languageScript.onload = () => document.dispatchEvent(new Event('DOMContentLoaded'));
          document.body.append(languageScript);
        };
        document.body.append(catalogue);
      } catch (_) {
        busy = false;
        alert(t('Не удалось переключить язык. Введённые данные сохранены на этой странице.'));
      }
      return;
    }
    try {
      sessionStorage.setItem(key, JSON.stringify({time: Date.now(), masterTab: document.querySelector('[name=calculator-detail-tabs]:checked')?.id, fields: all.filter(eligible).map(el => ({name:el.name,type:el.type,value:el.value,checked:el.checked}))}));
    } catch (_) {
      event.preventDefault();
      alert(t('Не удалось временно сохранить ввод. Завершите форму перед переключением языка.'));
      return;
    }
    form.querySelector('[name=next]').value = next.pathname + next.search + next.hash;
  }));
})();
