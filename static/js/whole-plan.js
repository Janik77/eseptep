/* Progressive enhancement: server authorizes and versions every calculation. No AI request here. */
(() => {
  let busy = false;
  const enhance = () => document.getElementById('whole-result')?.classList.add('whole-enhanced');
  const words = () => (document.getElementById('whole-result')?.dataset.language || '').startsWith('kk')
    ? ['Есеп жаңартылуда…', 'Материалдар мен сома жаңартылды.', 'Жаңарту орындалмады. Алдыңғы есеп көрсетілуде. Бетті жаңартып, қайталап көріңіз.']
    : ['Обновляем расчёт…', 'Материалы и сумма обновлены.', 'Не удалось обновить. Показан прежний результат. Обновите страницу и попробуйте снова.'];
  async function update(form) {
    if (busy || !form.reportValidity()) return;
    const root = document.getElementById('whole-result');
    const select = form.querySelector('select');
    const data = new FormData(form); // before disabling controls
    const oldScroll = window.scrollY;
    const focused = document.activeElement?.id;
    const expanded = [...root.querySelectorAll('details[open]')].map(x => x.id);
    const feedback = document.getElementById('whole-feedback');
    const labels = words();
    feedback.textContent = labels[0]; feedback.removeAttribute('data-error');
    busy = true; root.setAttribute('aria-busy', 'true');
    const controls = [...root.querySelectorAll('input,select,button')].filter(x => !x.disabled);
    controls.forEach(x => x.disabled = true);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(form.getAttribute('action') || location.href, {method:'POST', body:data,
        credentials:'same-origin', signal:controller.signal, headers:{'X-Requested-With':'XMLHttpRequest'}});
      const body = await response.text();
      if (!response.ok) {
        const reason = response.status === 400 && !body.includes('<') ? body.slice(0,240) : '';
        const failure = new Error(); failure.userReason = reason; throw failure;
      }
      const doc = new DOMParser().parseFromString(body, 'text/html');
      const updated = doc.getElementById('whole-result');
      if (!updated?.dataset.estimate || updated.querySelector('.whole-error')) throw new Error('');
      root.replaceWith(updated); enhance();
      expanded.forEach(id => { const item = document.getElementById(id); if (item?.tagName === 'DETAILS') item.open = true; });
      const nextFocus = focused && document.getElementById(focused);
      nextFocus?.focus({preventScroll:true});
      window.scrollTo({top:oldScroll, behavior:'instant'});
      document.getElementById('whole-feedback').textContent = labels[1];
    } catch (error) {
      if (select) select.value = select.dataset.previous;
      feedback.textContent = labels[2] + (error.userReason ? ' ' + error.userReason : '');
      feedback.setAttribute('data-error', 'true');
      window.scrollTo({top:oldScroll, behavior:'instant'});
    } finally {
      clearTimeout(timeout); controls.forEach(x => x.disabled = false);
      root.removeAttribute('aria-busy'); busy = false;
    }
  }
  document.addEventListener('change', event => {
    const form = event.target.closest('form[data-coverage]');
    if (form && event.target.matches('select')) update(form);
  });
  document.addEventListener('submit', event => {
    const form = event.target.closest('form[data-whole-update]');
    if (form) { event.preventDefault(); update(form); return; }
    const normal = event.target.closest('form[data-whole-submit]');
    if (!normal) return;
    if (normal.dataset.busy) { event.preventDefault(); return; }
    normal.dataset.busy = '1';
    normal.querySelectorAll('button[type=submit]').forEach(x => x.disabled = true);
    normal.querySelectorAll('[role=status]').forEach(x => x.hidden = false);
  });
  document.addEventListener('click', event => {
    if (busy && event.target.closest('#whole-result a')) event.preventDefault();
  });
  window.addEventListener('pageshow', () => {
    document.querySelectorAll('[data-whole-submit]').forEach(form => { delete form.dataset.busy; form.querySelectorAll('button').forEach(x => x.disabled = false); });
    enhance();
  });
  enhance();
})();
