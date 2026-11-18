// Keep the explicitly selected owned project when recalculating or changing language.
(() => {
  function bind() {
    const select = document.querySelector('select[name=project_id]');
    const hidden = document.querySelector('[data-calc-form] input[name=project_id]');
    if (!select || !hidden || select.dataset.meetingBound) return;
    select.dataset.meetingBound = '1';
    select.addEventListener('change', () => { hidden.value = select.value; });
    if (select.value) hidden.value = select.value;
  }
  document.addEventListener('DOMContentLoaded', bind); bind();
})();
