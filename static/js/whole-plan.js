/* UI-only guard: server remains authoritative for consent, stale versions and deduplication. */
(() => {
  const forms = () => document.querySelectorAll('[data-whole-submit]');
  function restore(form) {
    delete form.dataset.busy;
    form.removeAttribute('aria-busy');
    form.querySelectorAll('[data-submit-disabled]').forEach(button => {
      button.disabled = false;
      delete button.dataset.submitDisabled;
    });
    form.querySelectorAll('[role="status"]').forEach(status => { status.hidden = true; });
  }
  function bind() {
    forms().forEach(form => {
      if (form.dataset.wholeBound) return;
      form.dataset.wholeBound = '1';
      form.addEventListener('submit', event => {
        if (form.dataset.busy === '1') { event.preventDefault(); return; }
        if (!form.checkValidity()) return;
        form.dataset.busy = '1';
        form.setAttribute('aria-busy', 'true');
        form.querySelectorAll('button[type="submit"]:not(:disabled)').forEach(button => {
          button.dataset.submitDisabled = '1';
          button.disabled = true;
        });
        form.querySelectorAll('[role="status"]').forEach(status => { status.hidden = false; });
      });
    });
  }
  window.addEventListener('pageshow', () => { forms().forEach(restore); bind(); });
  document.addEventListener('DOMContentLoaded', bind);
  bind();
})();