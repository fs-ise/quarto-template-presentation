/*
 * Simplemenu for Reveal.js
 * Copyright (c) Martin Donath; distributed under the MIT license.
 */
var Simplemenu = (function () {
  "use strict";

  function init(deck) {
    var options = deck.getConfig().simplemenu || {};
    var reveal = document.querySelector(".reveal");
    var barhtml = options.barhtml || {};
    if (reveal && barhtml.header) {
      reveal.insertAdjacentHTML("afterbegin", barhtml.header);
    }
    if (reveal && barhtml.footer) {
      reveal.insertAdjacentHTML("beforeend", barhtml.footer);
    }
    var bars = document.querySelectorAll(".menubar");
    if (!bars.length) return;

    var groups = Array.prototype.filter.call(
      document.querySelectorAll(".reveal .slides section[data-name]"),
      function (section) {
        return !section.parentElement.closest("section[data-name]");
      }
    );

    bars.forEach(function (bar) {
      if (options.scale) bar.style.fontSize = options.scale + "em";
      var menu = bar.querySelector(".menu");
      if (!menu) return;
      menu.replaceChildren();
      groups.forEach(function (section) {
        var item = document.createElement("li");
        var link = document.createElement("a");
        link.textContent = section.dataset.name;
        link.href = "#/" + section.id;
        link.dataset.simplemenuTarget = section.id;
        item.appendChild(link);
        menu.appendChild(item);
      });
    });

    function update(event) {
      var current = event && event.currentSlide;
      var group = current && current.closest("section[data-name]");
      document.querySelectorAll("[data-simplemenu-target]").forEach(function (link) {
        var active = Boolean(group && link.dataset.simplemenuTarget === group.id);
        link.parentElement.classList.toggle("active", active);
        link.setAttribute("aria-current", active ? "true" : "false");
      });
      document.querySelectorAll(".menubar .slide-number").forEach(function (number) {
        number.textContent = (deck.getSlidePastCount() + 1) + " / " + deck.getTotalSlides();
      });
    }

    deck.on("ready", update);
    deck.on("slidechanged", update);
    update({ currentSlide: deck.getCurrentSlide() });
  }

  return { id: "simplemenu", init: init };
})();
