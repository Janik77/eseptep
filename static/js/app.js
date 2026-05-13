document.addEventListener('DOMContentLoaded', () => {
    const slider = document.querySelector('[data-slider]');

    if (slider) {
        const track = slider.querySelector('[data-slider-track]');
        const dots = [...slider.querySelectorAll('[data-slide-dot]')];

        if (track && dots.length > 0) {
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
    }

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
});
