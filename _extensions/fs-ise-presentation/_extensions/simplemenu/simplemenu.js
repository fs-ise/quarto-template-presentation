/*
 * Simplemenu for Reveal.js
 * Copyright (c) Martin Donath; distributed under the MIT license.
 */
var Simplemenu = (function () {
  "use strict";

  /* Keep the upstream Simplemenu convention: a stack may be named either on
     its horizontal wrapper or on one of its vertical slides. Quarto's
     section-divs output uses the latter form for attributes on level-1
     headings. */
  function stackNameSection(stack) {
    if (stack.hasAttribute("data-stack-name")) return stack;
    return stack.querySelector(":scope > section[data-stack-name]");
  }

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
    if (!bars.length) throw new Error("Simplemenu could not find a .menubar element");

    var groups = Array.prototype.map.call(
      document.querySelectorAll(".reveal .slides > section"),
      function (stack, horizontalIndex) {
        return { stack: stack, nameSection: stackNameSection(stack), h: horizontalIndex };
      }
    ).filter(function (group) {
      return group.nameSection;
    });

    if (!groups.length) {
      var detected = Array.prototype.map.call(
        document.querySelectorAll(".reveal .slides section[data-stack-name]"),
        function (section) { return section.dataset.stackName; }
      );
      throw new Error("Simplemenu found no named horizontal stacks; detected data-stack-name values: " + JSON.stringify(detected));
    }

    bars.forEach(function (bar) {
      if (options.scale) bar.style.fontSize = options.scale + "em";
      var menu = bar.querySelector(".menu");
      if (!menu) return;
      menu.replaceChildren();
      groups.forEach(function (group) {
        var item = document.createElement("li");
        var link = document.createElement("a");
        link.textContent = group.nameSection.dataset.stackName;
        link.href = "#/" + group.h;
        link.dataset.simplemenuTarget = String(group.h);
        item.appendChild(link);
        menu.appendChild(item);
      });
    });

    function update(event) {
      var current = event && event.currentSlide;
      var indices = current ? deck.getIndices(current) : null;
      document.querySelectorAll("[data-simplemenu-target]").forEach(function (link) {
        var active = Boolean(indices && link.dataset.simplemenuTarget === String(indices.h));
        link.parentElement.classList.toggle("active", active);
        link.setAttribute("aria-current", active ? "true" : "false");
      });
      document.querySelectorAll(".menubar .menu-slide-number").forEach(function (number) {
        number.textContent = (deck.getSlidePastCount() + 1) + " / " + deck.getTotalSlides();
      });
    }

    deck.on("ready", update);
    deck.on("slidechanged", update);
    update({ currentSlide: deck.getCurrentSlide() });

    return Promise.resolve();
  }

  return { id: "simplemenu", init: init };
})();
