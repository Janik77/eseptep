const tr = (text) => typeof gettext === 'function' ? gettext(text) : text;
document.documentElement.classList.add('js');

document.addEventListener('DOMContentLoaded', () => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    initReveal(prefersReducedMotion);
    initSlider();
    initParallax(prefersReducedMotion);
    initCalculatorForm();
    initResultFlow(prefersReducedMotion);
    initCountUp(prefersReducedMotion);
    initMasterTemplate();
    initVariantResults();
    initSingleResultCopy();
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

    const stale = document.querySelector('[data-result-stale]');
    const inputSignature = () => JSON.stringify([...new FormData(form)].filter(([name]) => !['csrfmiddlewaretoken','action','project_id'].includes(name)));
    const originalSignature = inputSignature();
    const updateStale = () => {
        if (!stale) return;
        const changed = originalSignature !== inputSignature();
        stale.hidden = !changed;
        document.querySelectorAll('[data-copy-variant], [data-copy-single], .result-actions--backend button[type="submit"]').forEach(button => {button.disabled = changed;});
    };
    form.addEventListener('input', updateStale);
    form.addEventListener('change', updateStale);

    const decimalInputs = [...form.querySelectorAll('[data-decimal-field="true"]')];
    const normalizeDecimalInputs = () => {
        decimalInputs.forEach((input) => {
            input.value = input.value.trim().replace(',', '.');
        });
    };

    form.addEventListener('submit', () => {
        normalizeDecimalInputs();

        const button = form.querySelector('[type="submit"]');
        form.classList.add('is-calculating');

        if (button) {
            button.dataset.originalText = button.textContent;
            button.textContent = tr('Считаем');
        }
    });
}


function initResultFlow(prefersReducedMotion = false) {
    const readyState = document.querySelector('[data-result-ready]');
    const resultCard = document.querySelector('#estimate-result');
    const saveButtons = [...document.querySelectorAll('[data-save-estimate]')];
    const feedback = document.querySelector('[data-save-feedback]');

    if (readyState && resultCard) {
        window.setTimeout(() => {
            resultCard.scrollIntoView({ behavior: prefersReducedMotion ? 'auto' : 'smooth', block: 'start' });
        }, 260);
    }

    saveButtons.forEach((button) => {
        button.addEventListener('click', async () => {
            const estimateText = button.dataset.estimateText || tr('Список материалов ESEPTEP');
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
                button.textContent = button.dataset.savedText || tr('Список сохранён');
            } catch (error) {
                button.textContent = tr('Список сохранён');
            }

            if (feedback) {
                feedback.textContent = tr('Список сохранён в браузере и скопирован. Можно отправить мастеру или продавцу.');
            }

            window.setTimeout(() => {
                button.textContent = button.dataset.originalText || tr('Сохранить список');
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
            element.textContent = `${prefix}${target.toLocaleString(document.documentElement.lang === 'kk' ? 'kk-KZ' : 'ru-RU')}${suffix}`;
            return;
        }

        const duration = 720;
        const startTime = performance.now();

        const tick = (now) => {
            const progress = Math.min((now - startTime) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(target * eased);
            element.textContent = `${prefix}${current.toLocaleString(document.documentElement.lang === 'kk' ? 'kk-KZ' : 'ru-RU')}${suffix}`;

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

    const output = builder.querySelector('[data-master-output]');
    const preview = builder.querySelector('[data-whatsapp-preview]');
    const totalElement = builder.querySelector('[data-builder-total]');
    const copyButton = builder.querySelector('[data-copy-template]');
    const toast = builder.querySelector('[data-copy-toast]');
    const whatsappLink = builder.querySelector('[data-whatsapp-link]');

    const getRows = () => [...builder.querySelectorAll('[data-material-row]')];
    const getPositiveRows = () => getRows().map((row) => {
        const materialNode = row.querySelector('[data-row-material]');
        const quantityInput = row.querySelector('[data-row-qty]');
        const unit = materialNode?.dataset.unit || row.querySelector('[data-row-total]')?.textContent?.trim() || '';
        const quantity = Math.max(Number(quantityInput?.value || 0), 0);

        return {
            material: materialNode?.dataset.value || materialNode?.textContent?.trim() || tr('Материал'),
            quantity,
            unit,
        };
    }).filter((item) => item.quantity > 0);

    const buildEstimate = () => {
        const filledRows = getPositiveRows();
        const lines = [tr('ESEPTEP · список материалов для мастера'), ''];

        if (filledRows.length === 0) {
            lines.push(tr('Заполните количество у нужных материалов — в список попадут только позиции больше 0.'));
        } else {
            filledRows.forEach((item, index) => {
                const quantityLabel = `${item.quantity.toLocaleString(document.documentElement.lang === 'kk' ? 'kk-KZ' : 'ru-RU')} ${item.unit}`.trim();
                lines.push(`${index + 1}. ${item.material} — ${quantityLabel}`);
            });
        }

        lines.push('');
        lines.push(tr('Цены не указаны. Количество нужно проверить по проекту.'));

        const text = lines.join('\n');

        if (totalElement) {
            totalElement.textContent = `${filledRows.length} / ${getRows().length} ${tr('заполнено')}`;
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

        return text;
    };

    const bindRow = (row) => {
        const quantityInput = row.querySelector('[data-row-qty]');
        const decreaseButton = row.querySelector('[data-step-decrease]');
        const increaseButton = row.querySelector('[data-step-increase]');

        quantityInput?.addEventListener('input', buildEstimate);

        decreaseButton?.addEventListener('click', () => {
            const current = Number(quantityInput.value || 0);
            quantityInput.value = Math.max(0, current - 1).toFixed(1);
            buildEstimate();
        });

        increaseButton?.addEventListener('click', () => {
            const current = Number(quantityInput.value || 0);
            quantityInput.value = (current + 1).toFixed(1);
            buildEstimate();
        });
    };

    getRows().forEach(bindRow);

    copyButton?.addEventListener('click', async () => {
        const text = buildEstimate();

        if (!output) {
            return;
        }

        const copied = await copyPlainText(text);
        showCopyFeedback(copyButton, toast, copied, tr('Скопировать список'));
    });

    buildEstimate();
}

function initVariantResults() {
    document.querySelectorAll('[data-variant-result]').forEach((root) => {
        const buttons = Array.from(root.querySelectorAll('[data-variant-button]'));
        const panels = Array.from(root.querySelectorAll('[data-variant-panel]'));
        const label = root.querySelector('[data-active-variant-label]');
        const resultCard = root.closest('.result-card');
        const summary = resultCard?.querySelector('[data-summary-variant]');
        const summaryTotal = resultCard?.querySelector('[data-summary-total]');
        const hiddenInputs = document.querySelectorAll('[data-selected-variant-input]');
        const copyButton = root.querySelector('[data-copy-variant]');
        const toast = root.querySelector('[data-variant-copy-toast]');
        let activeKey = buttons.find((button) => button.classList.contains('is-active'))?.dataset.variantButton || buttons[0]?.dataset.variantButton;

        const setActive = (key) => {
            activeKey = key;
            buttons.forEach((button) => {
                const isActive = button.dataset.variantButton === key;
                button.classList.toggle('is-active', isActive);
                button.setAttribute('aria-selected', String(isActive));
                if (isActive) {
                    const title = button.querySelector('b')?.textContent || '';
                    if (label) label.textContent = title;
                    if (summary) summary.textContent = `${title} · ${button.dataset.variantCount} ${tr('позиций · цены справочно')}`;
                    if (summaryTotal) summaryTotal.textContent = `${Number(button.dataset.variantTotal).toLocaleString('ru-RU').replace(/[\u00a0\u202f]/g, ' ')} ₸`;
                }
            });
            panels.forEach((panel) => {
                panel.classList.toggle('is-active', panel.dataset.variantPanel === key);
            });
            hiddenInputs.forEach((input) => {
                input.value = key;
            });
        };

        buttons.forEach((button) => {
            button.addEventListener('click', () => setActive(button.dataset.variantButton));
        });

        copyButton?.addEventListener('click', async () => {
            const source = root.querySelector(`[data-variant-copy-source="${activeKey}"]`);
            const text = source?.value || '';
            if (!text.trim()) {
                return;
            }

            const copied = await copyPlainText(text);
            showCopyFeedback(copyButton, toast, copied, tr('Скопировать список без цен'));
        });

        if (activeKey) {
            setActive(activeKey);
        }
    });
}


function initSingleResultCopy() {
    document.querySelectorAll('[data-copy-single]').forEach((button) => {
        const root = button.closest('.result-card') || document;
        const source = root.querySelector('[data-single-copy-source]');
        const toast = root.querySelector('[data-single-copy-toast]');

        button.addEventListener('click', async () => {
            const text = source?.value || '';
            if (!text.trim()) {
                return;
            }

            const copied = await copyPlainText(text);
            showCopyFeedback(button, toast, copied, tr('Скопировать список материалов без цен'));
        });
    });
}


// Hidden source textareas cannot be reliably selected. Keep fallback selection
// temporary, and only report success when the browser confirms the copy.
async function copyPlainText(text) {
    try {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(text);
            return true;
        }
    } catch (error) {
        // Clipboard permission can be denied; try the legacy user-gesture API.
    }
    let temporary;
    const previousFocus = document.activeElement;
    try {
        temporary = document.createElement('textarea');
        temporary.value = text;
        temporary.readOnly = true;
        temporary.setAttribute('aria-label', tr('Текст для копирования'));
        temporary.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;opacity:0.01;pointer-events:none;';
        document.body.appendChild(temporary);
        temporary.focus({preventScroll: true});
        temporary.select();
        temporary.setSelectionRange(0, text.length);
        return document.execCommand('copy') === true;
    } catch (error) {
        return false;
    } finally {
        temporary?.remove();
        previousFocus?.focus?.({preventScroll: true});
    }
}

function showCopyFeedback(button, toast, copied, originalLabel) {
    if (button.copyFeedbackTimer) window.clearTimeout(button.copyFeedbackTimer);
    button.classList.toggle('is-copied', copied);
    button.textContent = copied ? tr('Скопировано') : tr('Не удалось скопировать. Повторить');
    if (toast) {
        toast.textContent = copied ? tr('Список скопирован') : tr('Копирование недоступно. Проверьте разрешения браузера и повторите.');
        toast.classList.add('is-visible');
    }
    // Failure remains visible until a later attempt succeeds.
    if (copied) {
        button.copyFeedbackTimer = window.setTimeout(() => {
            button.classList.remove('is-copied');
            button.textContent = originalLabel;
            toast?.classList.remove('is-visible');
        }, 1800);
    }
}
