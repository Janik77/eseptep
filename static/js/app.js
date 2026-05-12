document.addEventListener('DOMContentLoaded', () => {
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
});
