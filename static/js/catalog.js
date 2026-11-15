/* Progressive enhancement: without JS every calculator remains a normal link. */
(() => {
  const tr = text => typeof gettext === 'function' ? gettext(text) : text;
  const toolbar = document.querySelector('[data-catalog-toolbar]');
  if (!toolbar) return;
  const cards = [...document.querySelectorAll('[data-work-card]')];
  const filters = [...toolbar.querySelectorAll('[data-filter]')];
  const search = toolbar.querySelector('[data-catalog-search]');
  const empty = document.querySelector('[data-catalog-empty]');
  const count = document.querySelector('[data-catalog-count]');
  let group = 'all';
  const normalize = value => value.toLocaleLowerCase('ru').replaceAll('ё', 'е').trim();
  const update = () => {
    const query = normalize(search.value);
    let visible = 0;
    for (const card of cards) {
      card.hidden = !(group === 'all' || card.dataset.group === group) || !normalize(card.textContent).includes(query);
      if (!card.hidden) visible += 1;
    }
    for (const button of filters) {
      const active = button.dataset.filter === group;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    }
    empty.hidden = visible !== 0;
    count.textContent = `${tr('Показано:')} ${visible} ${tr('из')} ${cards.length}`;
  };
  filters.forEach(button => button.addEventListener('click', () => { group = button.dataset.filter; update(); }));
  search.addEventListener('input', update);
  document.querySelector('[data-catalog-reset]').addEventListener('click', () => {
    group = 'all'; search.value = ''; update(); search.focus();
  });
  toolbar.hidden = false;
  update();
})();
