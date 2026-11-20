"""Install metadata and a deliberately data-free service worker."""
from django.conf import settings
from django.http import FileResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.utils.cache import add_never_cache_headers
from django.views.decorators.http import require_safe

COPY = {
    'ru': {
        'title': 'ESEPTEP на телефоне',
        'intro': 'Добавьте ESEPTEP на главный экран. Калькуляторы, проекты и сметы останутся в том же сервисе.',
        'install': 'Установить ESEPTEP',
        'installed': 'ESEPTEP открыт как приложение.',
        'android': 'Android · Chrome',
        'android_steps': ('Откройте ESEPTEP в Chrome.', 'В меню ⋮ выберите «Установить приложение» или «Добавить на главный экран», затем подтвердите.'),
        'ios': 'iPhone · Safari',
        'ios_steps': ('Откройте ESEPTEP в Safari и нажмите «Поделиться».', 'Выберите «На экран „Домой“». Если есть переключатель «Открывать как веб‑приложение», включите его, затем нажмите «Добавить».'),
        'online': 'Для расчётов, сохранения смет и доступа к проектам нужен интернет. Данные проекта не сохраняются для работы без сети. При необходимости войдите снова.',
        'home': 'На главную',
    },
    'kk': {
        'title': 'Телефондағы ESEPTEP',
        'intro': 'ESEPTEP-ті басты экранға қосыңыз. Калькуляторлар, жобалар мен сметалар сол сервисте қалады.',
        'install': 'ESEPTEP-ті орнату',
        'installed': 'ESEPTEP қолданба ретінде ашылды.',
        'android': 'Android · Chrome',
        'android_steps': ('ESEPTEP-ті Chrome браузерінде ашыңыз.', '⋮ мәзірінен «Қолданбаны орнату» немесе «Басты экранға қосу» тармағын таңдап, растаңыз.'),
        'ios': 'iPhone · Safari',
        'ios_steps': ('ESEPTEP-ті Safari браузерінде ашып, «Бөлісу» түймесін басыңыз.', '«Басты экранға қосу» тармағын таңдаңыз. «Веб-қолданба ретінде ашу» ауыстырып қосқышы болса, оны қосып, «Қосу» түймесін басыңыз.'),
        'online': 'Есептеулер, сметаны сақтау және жобаларды ашу үшін интернет қажет. Жоба деректері желіден тыс жұмыс үшін сақталмайды. Қажет болса, аккаунтқа қайта кіріңіз.',
        'home': 'Басты бетке',
    },
}


@require_safe
def install(request):
    return render(request, 'core/install.html', {'install_copy': COPY.get(request.LANGUAGE_CODE, COPY['ru'])})


@require_safe
def manifest(request):
    root = reverse('core:home')
    return JsonResponse({
        'id': root, 'name': 'ESEPTEP', 'short_name': 'ESEPTEP',
        'start_url': root, 'scope': root, 'display': 'standalone',
        'background_color': '#f7f8fa', 'theme_color': '#f7f8fa',
        'icons': [
            {'src': static('pwa/icon-192.png'), 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
            {'src': static('pwa/icon-512.png'), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
            {'src': static('pwa/icon-maskable-512.png'), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
        ],
    }, content_type='application/manifest+json', headers={'Cache-Control': 'no-cache'})


@require_safe
def worker(request):
    # Root scope is determined by the worker URL, not the static asset prefix.
    return FileResponse((settings.BASE_DIR / 'core' / 'pwa-worker.js').open('rb'),
                        content_type='text/javascript; charset=utf-8',
                        headers={'Cache-Control': 'no-cache'})



_PRIVATE_PREFIXES = ('/accounts/', '/projects/', '/admin/', '/dashboard/', '/marketplace/', '/media/')


def private_response_no_store(get_response):
    """Keep private/signed/form responses out of intermediary and HTTP caches."""
    def middleware(request):
        response = get_response(request)
        if (request.path_info.startswith(_PRIVATE_PREFIXES)
                or request.method not in {'GET', 'HEAD', 'OPTIONS'}
                or request.user.is_authenticated):
            add_never_cache_headers(response)
        return response
    return middleware
