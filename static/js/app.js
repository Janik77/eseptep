document.documentElement.classList.add('js');

document.addEventListener('DOMContentLoaded', () => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    initReveal(prefersReducedMotion);
    initSlider();
    initParallax(prefersReducedMotion);
    initCalculatorForm();
    initCountUp(prefersReducedMotion);
    initMasterTemplate();
});

function initReveal(prefersReducedMotion) {
    const revealTargets = document.querySelectorAll([
        '.page-hero',
        '.repair-chip',
        '.feature-card',
        '.calculator-card',
        '.service-card',
        '.project-upload-card',
        '.calculator-workspace',
        '.master-template',
        '.skeleton-section',
    ].join(','));

    revealTargets.forEach((element, index) => {
        element.classList.add('reveal');
        element.style.setProperty('--reveal-delay', `${Math.min(index * 45, 260)}ms`);
    });

    if (prefersReducedMotion || !('IntersectionObserver' in window)) {
        revealTargets.forEach((element) => element.classList.add('is-visible'));
        return;
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) {
                return;
            }

            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
        });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

    revealTargets.forEach((element) => observer.observe(element));
}

function initSlider() {
    const slider = document.querySelector('[data-slider]');

    if (!slider) {
        return;
    }

    const track = slider.querySelector('[data-slider-track]');
    const dots = [...slider.querySelectorAll('[data-slide-dot]')];

    if (!track || dots.length === 0) {
        return;
    }

    const setActiveDot = () => {
        const slideWidth = track.scrollWidth / dots.length;
        const activeIndex = Math.min(
            dots.length - 1,
            Math.max(0, Math.round(track.scrollLeft / slideWidth)),
        );

        dots.forEach((dot, index) => {
            dot.classList.toggle('is-active', index === activeIndex);
        });
    };

    dots.forEach((dot, index) => {
        dot.addEventListener('click', () => {
            const slideWidth = track.scrollWidth / dots.length;
            track.scrollTo({ left: slideWidth * index, behavior: 'smooth' });
        });
    });

    track.addEventListener('scroll', () => window.requestAnimationFrame(setActiveDot), { passive: true });
    window.addEventListener('resize', setActiveDot);
    setActiveDot();
}

function initParallax(prefersReducedMotion) {
    const heroPhoto = document.querySelector('[data-parallax-bg]');

    if (!heroPhoto || prefersReducedMotion) {
        return;
    }

    const updateParallax = () => {
        const offset = Math.min(window.scrollY * 0.08, 26);
        heroPhoto.style.transform = `scale(1.04) translateY(${offset}px)`;
    };

    window.addEventListener('scroll', () => window.requestAnimationFrame(updateParallax), { passive: true });
    updateParallax();
}

function initCalculatorForm() {
    const form = document.querySelector('[data-calc-form]');

    if (!form) {
        return;
    }

    form.addEventListener('submit', () => {
        const button = form.querySelector('[type="submit"]');
        form.classList.add('is-calculating');

        if (button) {
            button.dataset.originalText = button.textContent;
            button.textContent = 'Считаем';
        }
    });
}

function initCountUp(prefersReducedMotion) {
    const numbers = [...document.querySelectorAll('[data-count-up]')];

    if (numbers.length === 0) {
        return;
    }

    const animateNumber = (element) => {
        const target = Number(element.dataset.countUp);
        const prefix = element.dataset.countPrefix || '';
        const suffix = element.dataset.countSuffix || '';

        if (!Number.isFinite(target) || prefersReducedMotion) {
            element.textContent = `${prefix}${target.toLocaleString('ru-RU')}${suffix}`;
            return;
        }

        const duration = 720;
        const startTime = performance.now();

        const tick = (now) => {
            const progress = Math.min((now - startTime) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(target * eased);
            element.textContent = `${prefix}${current.toLocaleString('ru-RU')}${suffix}`;

            if (progress < 1) {
                window.requestAnimationFrame(tick);
            }
        };

        window.requestAnimationFrame(tick);
    };

    if (!('IntersectionObserver' in window)) {
        numbers.forEach(animateNumber);
        return;
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) {
                return;
            }

            animateNumber(entry.target);
            observer.unobserve(entry.target);
        });
    }, { threshold: 0.45 });

    numbers.forEach((element) => observer.observe(element));
}

function initMasterTemplate() {
    const materialSelect = document.querySelector('[data-master-material]');
    const quantityInput = document.querySelector('[data-master-qty]');
    const output = document.querySelector('[data-master-output]');
    const copyButton = document.querySelector('[data-copy-template]');

    const updateMasterTemplate = () => {
        if (!materialSelect || !quantityInput || !output) {
            return;
        }

        output.value = [
            `Материал: ${materialSelect.value}`,
            `Количество: ${quantityInput.value}`,
            'Объект: квартира',
            'Комментарий: подготовьте цену и сроки.',
        ].join('\n');
    };

    materialSelect?.addEventListener('change', updateMasterTemplate);
    quantityInput?.addEventListener('input', updateMasterTemplate);
    copyButton?.addEventListener('click', async () => {
        updateMasterTemplate();
        if (!output) {
            return;
        }

        try {
            await navigator.clipboard.writeText(output.value);
            copyButton.textContent = 'Скопировано';
            window.setTimeout(() => {
                copyButton.textContent = 'Копировать список';
            }, 1600);
        } catch (error) {
            output.select();
            document.execCommand('copy');
        }
    });
}
