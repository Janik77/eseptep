/* No Cache Storage, Background Sync, API, photos, private HTML or request replay. */
const OFFLINE = `<!doctype html>
<html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#f7f8fa"><title>ESEPTEP · Offline</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f7f8fa;color:#202936;font:16px/1.6 system-ui,sans-serif;min-height:100dvh;display:grid;place-items:center;padding:max(20px,env(safe-area-inset-top)) max(20px,env(safe-area-inset-right)) max(20px,env(safe-area-inset-bottom)) max(20px,env(safe-area-inset-left))}main{width:min(100%,460px);border:1px solid #dce2e9;background:#fff;border-radius:16px;padding:24px}h1,h2{font-size:1.28rem;line-height:1.25}strong,a{color:#315f9a}a{display:inline-flex;align-items:center;min-height:44px}a:focus-visible{outline:2px solid #315f9a;outline-offset:4px}section+section{border-top:1px solid #dce2e9;margin-top:20px}
</style>
<main><strong>ESEPTEP</strong>
<section><h1>Нет подключения</h1><p>Калькуляторы, проекты и сметы доступны только через интернет.</p><a href="/">На главную</a></section>
<section lang="kk"><h2>Интернет байланысы жоқ</h2><p>Калькуляторлар, жобалар мен сметалар интернет арқылы ғана қолжетімді.</p><a href="/">Басты бетке</a></section>
</main></html>`;
const PUBLIC_PAGES = new Set(['/', '/install/', '/calculators/']);
self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});
self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET' || request.mode !== 'navigate') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.search || !PUBLIC_PAGES.has(url.pathname)) return;
  event.respondWith(fetch(request, { cache: 'no-store' }).catch(() => new Response(OFFLINE, {
    status: 503,
    headers: {
      'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store',
      'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'",
    },
  })));
});
