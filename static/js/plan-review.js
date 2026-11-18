/* Presentation-only submit guard. Server deduplication remains authoritative. */
(() => {
  function bind() {
    document.querySelectorAll('[data-plan-analysis-form]').forEach(form => {
      if (form.dataset.bound) return;
      form.dataset.bound = '1';
      form.addEventListener('submit', event => {
        if (form.dataset.busy === '1') { event.preventDefault(); return; }
        form.dataset.busy = '1';
        form.setAttribute('aria-busy', 'true');
        form.querySelector('button[type=submit]').disabled = true;
        form.querySelector('[role=status]').hidden = false;
      });
    });
  }
  document.addEventListener('DOMContentLoaded', bind);
  window.addEventListener('pageshow', () => {
    document.querySelectorAll('[data-plan-analysis-form]').forEach(form => {
      delete form.dataset.busy;
      form.removeAttribute('aria-busy');
      form.querySelector('button[type=submit]').disabled = false;
      form.querySelector('[role=status]').hidden = true;
    });
    bind();
  });
  bind();
})();
