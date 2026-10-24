(() => {
  const cards = [...document.querySelectorAll("[data-album-photo]")];
  const lightbox = document.querySelector("[data-album-lightbox]");
  const image = document.querySelector("[data-album-lightbox-image]");
  const caption = document.querySelector("[data-album-lightbox-caption]");
  const closeButton = document.querySelector("[data-album-close]");
  const prevButton = document.querySelector("[data-album-prev]");
  const nextButton = document.querySelector("[data-album-next]");

  if (!cards.length || !lightbox || !image) return;

  let currentIndex = 0;

  function showPhoto(index) {
    currentIndex = (index + cards.length) % cards.length;
    const card = cards[currentIndex];
    const text = card.dataset.caption || "";
    image.src = card.dataset.src;
    image.alt = text;
    if (caption) caption.textContent = text;
  }

  function openLightbox(index) {
    showPhoto(index);
    lightbox.hidden = false;
    document.body.classList.add("album-lightbox-open");
    closeButton?.focus();
  }

  function closeLightbox() {
    lightbox.hidden = true;
    document.body.classList.remove("album-lightbox-open");
    image.removeAttribute("src");
    cards[currentIndex]?.focus();
  }

  cards.forEach((card, index) => {
    card.addEventListener("click", () => openLightbox(index));
  });

  closeButton?.addEventListener("click", closeLightbox);
  prevButton?.addEventListener("click", () => showPhoto(currentIndex - 1));
  nextButton?.addEventListener("click", () => showPhoto(currentIndex + 1));
  lightbox.addEventListener("click", (event) => {
    if (event.target === lightbox) closeLightbox();
  });

  document.addEventListener("keydown", (event) => {
    if (lightbox.hidden) return;
    if (event.key === "Escape") closeLightbox();
    if (event.key === "ArrowLeft") showPhoto(currentIndex - 1);
    if (event.key === "ArrowRight") showPhoto(currentIndex + 1);
  });
})();
