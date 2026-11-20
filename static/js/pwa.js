(() => {
  const worker = document.currentScript?.dataset.pwaWorker;
  const button = document.querySelector('[data-install-app]');
  const installed = document.querySelector('[data-installed-app]');
  const displayMode = matchMedia('(display-mode: standalone)');
  const standalone = () => displayMode.matches || navigator.standalone === true;
  function refreshMode() {
    const active = standalone();
    document.documentElement.toggleAttribute('data-pwa-standalone', active);
    if (installed) installed.hidden = !active;
    if (button && active) button.hidden = true;
  }
  refreshMode();
  displayMode.addEventListener?.('change', refreshMode);
  if (worker && window.isSecureContext && 'serviceWorker' in navigator) {
    navigator.serviceWorker.register(worker).catch(() => {}); // Normal Django navigation still works.
  }
  if (!button || standalone()) return;
  let promptEvent = null;
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    promptEvent = event;
    button.hidden = false;
  });
  button.addEventListener('click', async () => {
    if (!promptEvent) return;
    const prompt = promptEvent;
    promptEvent = null;
    button.disabled = true;
    try { await prompt.prompt(); } catch { /* Browser menu instructions remain available. */ }
    finally { button.hidden = true; button.disabled = false; }
  });
  window.addEventListener('appinstalled', () => { promptEvent = null; button.hidden = true; });
})();
