# AGENTS.md

## Project Overview

This repository provides a reusable **Quarto Reveal.js presentation template** with Frankfurt School branding, navigation, and slide layouts.

- `template.qmd`: Example presentation
- `_extensions/`: Quarto presentation extension
- `copier-template/`, `copier.yml`: Copier project template
- `tests/`: Automated tests

## General Guidelines

- Prefer **native Quarto and Reveal.js features** over custom JavaScript.
- Keep changes minimal, maintainable, and reusable across presentations.
- Preserve existing branding, navigation, and responsive scaling.
- Avoid hardcoded pixel dimensions where responsive layouts are possible.
- Use level-2 headings (`##`) for slides. Do not use them inside columns or nested layouts.
- Use `data-name` on section-opening slides for flat navigation.
- Check rendered slides for alignment, clipping, readability, and overflow.

## Figures and SVGs

- Prefer SVG for diagrams, illustrations, and other vector graphics.
- **Always crop SVG whitespace** by adjusting the `viewBox` or document bounds. Excess whitespace can cause scaling and positioning issues.
- Preserve aspect ratios and use consistent dimensions for related figures.
- Avoid unnecessary rasterization and CSS-based scaling workarounds.
- Verify SVG positioning in the rendered presentation.

### SVG Animation in Reveal.js Slides

Animate SVG diagrams using **sequential SVG snapshots and Reveal.js fragments**, rather than JavaScript animations.

- Create numbered SVG files (`diagram_0.svg`, `diagram_1.svg`, etc.), each representing one animation state.
- Overlay SVGs in a `position: relative` container, with each image using `position: absolute` and identical dimensions.
- Use Reveal.js fragment classes (`fragment`, `fade-out`, `current-visible`) and synchronized `data-fragment-index` values to transition between states.
- Keep SVG dimensions, alignment, and layout consistent to avoid visual jumps.
- Prefer this approach for progressively revealing diagram elements, relationships, or conceptual changes.

**Reference:** [Session 9 – Spohrer et al. example](https://github.com/fs-ise/machine-learning-for-big-data/blob/main/slides/session_09.qmd).

## Validation

Render and visually inspect affected slides before completing changes.

```bash
quarto render template.qmd
quarto preview template.qmd
```

Run relevant automated tests:

```bash
make test-static
make test-render
make test-browser
```

Use `make test` for comprehensive validation.

Check that changes work in both the repository example and Copier-generated presentations. Avoid committing generated output or temporary files.
