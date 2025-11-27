<script>
(function () {
  function updateHeader() {
    if (!window.Reveal) return;

    const slide = Reveal.getCurrentSlide();
    if (!slide) return;

    const logoEl = document.querySelector("#fs-header img");
    if (!logoEl) return;

    const isIntro = slide.classList.contains("firstIntro");

    // Hide logo on intro slide, show it otherwise
    logoEl.style.display = isIntro ? "none" : "";
  }

  Reveal.on("ready", updateHeader);
  Reveal.on("slidechanged", updateHeader);
})();
</script>
`
