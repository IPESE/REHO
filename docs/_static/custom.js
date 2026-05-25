document.addEventListener("DOMContentLoaded", function () {
    var path = window.location.pathname;
    var isModelPage = path.includes('/sections/model/');
    var isModelIndex = path.endsWith('/model/index.html') || path.endsWith('/model/');

    // ── Model index: full-width article, no right sidebar ────────────────────
    if (isModelIndex) {
        document.body.classList.add('model-index');
    }

    if (!isModelPage) { return; }

    // ── Lightbox setup ────────────────────────────────────────────────────────
    var overlay = document.createElement('div');
    overlay.id = 'lb-overlay';
    var lbImg = document.createElement('img');
    lbImg.id = 'lb-img';
    lbImg.alt = '';
    overlay.appendChild(lbImg);
    document.body.appendChild(overlay);

    function openLb(src) {
        lbImg.src = src;
        void overlay.offsetWidth;   // force reflow so CSS transition fires
        overlay.classList.add('active');
    }
    function closeLb() {
        overlay.classList.remove('active');
    }
    overlay.addEventListener('click', closeLb);
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { closeLb(); }
    });

    function applyLightbox(img) {
        img.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            openLb(img.src);
        });
    }

    // ── Index page: graphical overview images ─────────────────────────────────
    if (isModelIndex) {
        document.querySelectorAll('img.model-graphical-overview').forEach(applyLightbox);
        return;
    }

    // ── Building / District / Actors: all article figures ────────────────────
    document.querySelectorAll('.bd-article figure img').forEach(applyLightbox);
});
