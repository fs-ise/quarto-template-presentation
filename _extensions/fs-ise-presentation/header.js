<script>
(function () {
  function updateHeader() {
    if (!window.Reveal) return;

    const slide = Reveal.getCurrentSlide();
    if (!slide) return;

    const logoEl = document.querySelector("#fs-header img");
    if (!logoEl) return;

    const titleEl = document.querySelector("#slide-title-display");
    const heading = slide.querySelector("h2");
    if (titleEl) titleEl.textContent = heading ? heading.textContent : "";

    const isIntro = slide.classList.contains("firstIntro");

    // Hide logo on intro slide, show it otherwise
    logoEl.style.display = isIntro ? "none" : "";
  }

  Reveal.on("ready", updateHeader);
  Reveal.on("slidechanged", updateHeader);
})();
</script>
