document.documentElement.classList.add('js');

document.addEventListener('DOMContentLoaded', () => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    initReveal(prefersReducedMotion);
    initSlider();
    initParallax(prefersReducedMotion);
    initCalculatorForm();
    initResultFlow();
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
        '.flow-panel',
        '.success-state',
        '.calculator-workspace',
        '.post-flow-grid',
        '.recommendation-card',
        '.seller-card',
        '.store-card',
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


function initResultFlow() {
    const readyState = document.querySelector('[data-result-ready]');
    const resultCard = document.querySelector('#estimate-result');
    const saveButtons = [...document.querySelectorAll('[data-save-estimate]')];
    const feedback = document.querySelector('[data-save-feedback]');

    if (readyState && resultCard) {
        window.setTimeout(() => {
            resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 260);
    }

    saveButtons.forEach((button) => {
        button.addEventListener('click', async () => {
            const estimateText = button.dataset.estimateText || 'Список материалов ESEPTEP';
            const storagePayload = {
                text: estimateText,
                savedAt: new Date().toISOString(),
            };

            try {
                window.localStorage.setItem('eseptep:last-estimate', JSON.stringify(storagePayload));
            } catch (error) {
                // Local storage may be unavailable in private mode; copying still works.
            }

            try {
                await navigator.clipboard.writeText(estimateText);
                button.textContent = button.dataset.savedText || 'Список сохранён';
            } catch (error) {
                button.textContent = 'Список сохранён';
            }

            if (feedback) {
                feedback.textContent = 'Список сохранён в браузере и скопирован. Можно отправить мастеру или продавцу.';
            }

            window.setTimeout(() => {
                button.textContent = button.dataset.originalText || 'Сохранить список';
            }, 1800);
        });

        button.dataset.originalText = button.textContent;
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
    const builder = document.querySelector('[data-estimate-builder]');

    if (!builder) {
        return;
    }

    const rowsContainer = builder.querySelector('[data-material-rows]');
    const output = builder.querySelector('[data-master-output]');
    const preview = builder.querySelector('[data-whatsapp-preview]');
    const totalElement = builder.querySelector('[data-builder-total]');
    const copyButton = builder.querySelector('[data-copy-template]');
    const addButton = builder.querySelector('[data-add-material]');
    const toast = builder.querySelector('[data-copy-toast]');
    const whatsappLink = builder.querySelector('[data-whatsapp-link]');

    const formatCurrency = (value) => `₸ ${Math.round(value).toLocaleString('ru-RU')}`;

    const getRows = () => [...builder.querySelectorAll('[data-material-row]')];

    const buildEstimate = () => {
        const lines = ['ESEPTEP · список материалов для мастера', ''];
        let total = 0;

        getRows().forEach((row, index) => {
            const materialSelect = row.querySelector('[data-row-material]');
            const quantityInput = row.querySelector('[data-row-qty]');
            const totalNode = row.querySelector('[data-row-total]');
            const selectedOption = materialSelect?.selectedOptions?.[0];
            const material = materialSelect?.value || 'Материал';
            const quantity = Math.max(Number(quantityInput?.value || 0), 0);
            const price = Number(selectedOption?.dataset.price || 0);
            const rowTotal = quantity * price;

            total += rowTotal;

            if (totalNode) {
                totalNode.textContent = formatCurrency(rowTotal);
            }

            lines.push(`${index + 1}. ${material}`);
            lines.push(`   Кол-во: ${quantity.toLocaleString('ru-RU')} · Цена: ${formatCurrency(price)} · Сумма: ${formatCurrency(rowTotal)}`);
        });

        lines.push('');
        lines.push(`Итого по материалам: ${formatCurrency(total)}`);
        lines.push('Комментарий: подготовьте цену, сроки и наличие.');

        const text = lines.join('\n');

        if (totalElement) {
            totalElement.textContent = formatCurrency(total);
        }

        if (output) {
            output.value = text;
        }

        if (preview) {
            preview.textContent = text;
        }

        if (whatsappLink) {
            whatsappLink.href = `https://wa.me/?text=${encodeURIComponent(text)}`;
        }
    };

    const bindRow = (row) => {
        const materialSelect = row.querySelector('[data-row-material]');
        const quantityInput = row.querySelector('[data-row-qty]');
        const decreaseButton = row.querySelector('[data-step-decrease]');
        const increaseButton = row.querySelector('[data-step-increase]');
        const removeButton = row.querySelector('[data-remove-row]');

        materialSelect?.addEventListener('change', buildEstimate);
        quantityInput?.addEventListener('input', buildEstimate);

        decreaseButton?.addEventListener('click', () => {
            const current = Number(quantityInput.value || 0);
            quantityInput.value = Math.max(0.1, current - 1).toFixed(1);
            buildEstimate();
        });

        increaseButton?.addEventListener('click', () => {
            const current = Number(quantityInput.value || 0);
            quantityInput.value = (current + 1).toFixed(1);
            buildEstimate();
        });

        removeButton?.addEventListener('click', () => {
            if (getRows().length === 1) {
                quantityInput.value = '0.1';
                buildEstimate();
                return;
            }

            row.remove();
            buildEstimate();
        });
    };

    getRows().forEach(bindRow);

    addButton?.addEventListener('click', () => {
        const firstRow = getRows()[0];

        if (!firstRow || !rowsContainer) {
            return;
        }

        const newRow = firstRow.cloneNode(true);
        const quantityInput = newRow.querySelector('[data-row-qty]');
        const materialSelect = newRow.querySelector('[data-row-material]');

        if (quantityInput) {
            quantityInput.value = '1.0';
        }

        if (materialSelect) {
            materialSelect.selectedIndex = 0;
        }

        rowsContainer.appendChild(newRow);
        bindRow(newRow);
        buildEstimate();
    });

    copyButton?.addEventListener('click', async () => {
        buildEstimate();

        if (!output) {
            return;
        }

        try {
            await navigator.clipboard.writeText(output.value);
        } catch (error) {
            output.select();
            document.execCommand('copy');
        }

        copyButton.classList.add('is-copied');
        copyButton.textContent = 'Скопировано';
        toast?.classList.add('is-visible');

        window.setTimeout(() => {
            copyButton.classList.remove('is-copied');
            copyButton.textContent = 'Копировать список';
            toast?.classList.remove('is-visible');
        }, 1800);
    });

    buildEstimate();
}
