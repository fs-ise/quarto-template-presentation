# FS-ISE Presentation Extension for Quarto

`fs-ise-presentation` is a reusable [Quarto](https://quarto.org/) extension for
building Frankfurt School ISE presentations with reveal.js. It provides the
FS visual identity, a responsive logo and slide-title header, branded progress
and slide-number elements, and presentation-friendly sizing and typography.

See [`template.qmd`](template.qmd) for a compact, renderable presentation that
demonstrates the format's main features.

## Prerequisites

- [Quarto](https://quarto.org/docs/get-started/) **1.8.0 or newer**, as required
  by the extension manifest.

No additional language runtime or package manager is required.

## Create a new presentation from the template

Run this in the directory where you want Quarto to create the presentation:

```bash
quarto use template fs-ise/quarto-template-presentation
```

Follow the prompts to choose a target directory. This command creates a new
presentation from this repository's starter document and installs the
extension alongside it.

## Add the extension to an existing project

From the root of an existing Quarto project, run:

```bash
quarto add fs-ise/quarto-template-presentation
```

Unlike `quarto use template`, `quarto add` installs the extension into the
project's `_extensions/` directory without creating a new presentation. Use
the contributed format in a `.qmd` file as follows:

```yaml
---
title: "My presentation"
author: "Your name"
format: fs-ise-presentation-revealjs
---
```

Use level-two headings (`##`) for slides because the extension's slide level
is fixed to level 2 by default.

## Render and preview

Render a presentation once:

```bash
quarto render presentation.qmd
```

Start a local preview that refreshes when source files change:

```bash
quarto preview presentation.qmd
```

Both commands write reveal.js HTML using the format selected in the document
metadata.

## Format options

The extension inherits all
[reveal.js presentation options](https://quarto.org/docs/presentations/revealjs/)
and supplies these defaults from its manifest:

| Option | Default | Purpose |
| --- | --- | --- |
| `theme` | `[simple, custom.scss]` | Uses reveal.js's Simple theme plus the FS-ISE styles. |
| `include-before-body` | `header.html` | Adds the branded presentation header. |
| `include-after-body` | `header.js` | Updates the header as slides change. |
| `width` | `1600` | Sets the logical slide width. |
| `height` | `900` | Sets the logical slide height. |
| `lazy-load` | `true` | Lazily loads supported media. |
| `slide-number` | `true` | Displays slide numbers. |
| `auto-stretch` | `false` | Prevents automatic stretching of media. |
| `slide-level` | `2` | Starts a new slide at each level-two heading. |
| `format-resources` | `fs_logo_blue.svg` | Makes the FS logo available to rendered output. |

Override reveal.js options in the document YAML while retaining the extension
format, for example:

```yaml
format:
  fs-ise-presentation-revealjs:
    transition: fade
    slide-number: c/t
```

For project-specific styling, add your own CSS or SCSS through document or
project metadata rather than editing the installed extension. This keeps local
customizations separate and makes extension updates easier.

## Installations and updates

The extension is copied into each project, so every project controls its own
installed version.

- **Install in an existing project:** run
  `quarto add fs-ise/quarto-template-presentation` from that project's root.
- **Update the installed extension:** run
  `quarto update extension fs-ise/quarto-template-presentation`. This replaces
  the installed extension files with the latest available version.
- **Install a specific release or Git reference:** append it after `@`, for
  example `quarto add fs-ise/quarto-template-presentation@v1.0.0` or
  `quarto add fs-ise/quarto-template-presentation@main`.

Updating the extension updates files under `_extensions/`; it does **not**
overwrite individual presentation `.qmd` files. Presentation content therefore
remains under your control. If a newer starter example contains useful changes,
compare it with [`template.qmd`](template.qmd) and adopt those changes manually.

Commit `_extensions/fs-ise-presentation/` with your project when you want builds
to use the same extension version everywhere.
