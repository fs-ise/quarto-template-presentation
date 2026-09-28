# FS-ISE Presentation Extension for Quarto

`fs-ise-presentation` is a reusable [Quarto](https://quarto.org/) extension for
building Frankfurt School ISE presentations with reveal.js. It provides the
FS visual identity, a responsive logo header, branded progress
and slide-number elements, and presentation-friendly sizing and typography.

See [`template.qmd`](template.qmd) for a compact, renderable presentation that
demonstrates the format's main features.

The extension embeds
[Simplemenu](https://github.com/martinomagnifico/quarto-simplemenu) using
Quarto's nested `_extensions` mechanism. It is installed atomically with the
FS extension, so neither this repository nor a consuming project needs a
second `quarto add` command. The project configuration renders its
Introduction, Formatting, and Examples groups as the navigation menu.
Simplemenu is registered as a reveal.js plugin by the presentation extension;
documents should not also add it to `filters`. The embedded source retains its
upstream MIT license and attribution.

## Cover page

Every presentation gets a full-bleed cover automatically: the packaged
Frankfurt School image fills the complete 1600 × 900 slide without distortion,
and the title information is left-aligned and vertically centered over its
lighter right-hand area. The Frankfurt School logo sits directly on that
background at the upper left. Ordinary slides place the same-size logo at the
upper right as a non-interactive decorative image, with a reserved content
column that prevents text and figures from overlapping it. Both assets are part
of the extension, so they are installed
with `quarto add`; projects do not need to supply separate assets.

To replace the image for one document, set `cover-image` in its YAML metadata.
The path is relative to that document (or may be a project-relative path):

```yaml
---
title: "My presentation"
cover-image: images/my-cover.png
format: fs-ise-presentation-revealjs
---
```

Keep the replacement image in the presentation project so that it is available
when the rendered deck is published. Omitting `cover-image` restores the
extension's `figures/title_background.png` default.

## Prerequisites

- [Quarto](https://quarto.org/docs/get-started/) **1.8.0 or newer**, as required
  by the extension manifest.
- [Copier](https://copier.readthedocs.io/) is needed only for the configurable
  project workflow. Install it with `pipx install copier` (recommended) or
  `python -m pip install --user copier`.

Copier is not required to install the extension or use the simple Quarto
template.

## View the example presentation

[`template.qmd`](template.qmd) is the canonical demonstration of the format.
You can [view the latest rendered presentation on GitHub
Pages](https://fs-ise.github.io/quarto-template-presentation/) without
installing Quarto or Copier.

To work on the example locally, clone this repository and run:

```bash
quarto preview template.qmd
```

The preview build is independent of Copier: CI renders `template.qmd`
directly, publishes it to GitHub Pages, and packages its HTML and local
resources as a downloadable artifact.

## Install the Quarto extension

Add the format and its embedded Simplemenu integration to an existing Quarto
project:

```bash
quarto add fs-ise/quarto-template-presentation
```

This installs the extension into the project's `_extensions/` directory
without creating or replacing a presentation. Use it in a `.qmd` file as
follows:

```yaml
---
title: "My presentation"
author: "Your name"
format: fs-ise-presentation-revealjs
---
```

Use level-two headings (`##`) for slides because the extension's slide level
is fixed to level 2 by default.

If you prefer Quarto's starter-template workflow, run this in the directory
where you want Quarto to create the presentation:

```bash
quarto use template fs-ise/quarto-template-presentation
```

Follow the prompts to choose a target directory. This command creates a new
presentation from this repository's starter document and installs the
extension alongside it.

## Create a configurable project with Copier

Copier prompts for a project name, presentation title, author, and optional
subtitle:

```bash
copier copy --trust gh:fs-ise/quarto-template-presentation my-talk
cd my-talk
quarto render
```

Approve the trusted template task when prompted. From the generated project's
directory, it runs noninteractive `quarto add` commands to install the
published `fs-ise-presentation` extension as well as the separate
[QRcode](https://github.com/jmbuhr/quarto-qrcode) and
[Iconify](https://github.com/mcanouil/quarto-iconify) extensions. Simplemenu
is embedded in `fs-ise-presentation` and is configured there as a bottom menu
and automatically derives its links from level-one slide sections. The same
settings therefore apply to the repository example and generated projects,
without duplicate document or project configuration. Third-party sources are
not duplicated in the Copier template.
The generated project includes `presentation.qmd`, `_quarto.yml`, `README.md`,
`Makefile`, and a `figures/` directory. For unattended generation, provide
answers with Copier's `--data` options and pass `--trust`.

To preview while editing:

```bash
cd my-talk
quarto preview
```

## Render locally

From this repository's root, render the example once or start its live preview:

```bash
quarto render template.qmd
quarto preview
```

In a Copier-generated project's root, the project configuration selects
`presentation.qmd`, so the equivalent commands are:

```bash
quarto render
quarto preview
```

Both commands write reveal.js HTML using the format selected in the document
metadata.

## Download the rendered example

GitHub Actions renders and packages the example on every pull request and every
push to `main`. To download it, open the repository's **Actions** tab, select a
successful **Render presentation** run, and download the
`presentation-html` artifact from the run's **Artifacts** section. Extract the
archive, then open `index.html` (or `template.html`) in a browser. The artifact
includes the reveal.js dependencies, styles, fonts, logos, and background
images needed to view the presentation locally without running a web server.

## Format options

The extension inherits all
[reveal.js presentation options](https://quarto.org/docs/presentations/revealjs/)
and supplies these defaults from its manifest:

| Option | Default | Purpose |
| --- | --- | --- |
| `theme` | `[simple, custom.scss]` | Uses reveal.js's Simple theme plus the FS-ISE styles. |
| `include-before-body` | `header.html` | Adds the branded presentation header. |
| `width` | `1600` | Sets the logical slide width. |
| `height` | `900` | Sets the logical slide height. |
| `lazy-load` | `true` | Lazily loads supported media. |
| `slide-number` | `true` | Displays slide numbers. |
| `section-divs` | `true` | Preserves level-one groups for Simplemenu navigation. |
| `revealjs-plugins` | `[simplemenu]` | Registers and initializes Simplemenu with reveal.js. |
| `auto-stretch` | `false` | Prevents automatic stretching of media. |
| `slide-level` | `2` | Starts a new slide at each level-two heading. |
| `template-partials` | `title-slide.html` | Builds the reusable full-bleed cover. |
| `format-resources` | `figures/` | Preserves the shared asset directory in the project and rendered output. |

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

### Update a Copier-generated project

The Quarto extensions and Copier scaffolding have separate update lifecycles.
From the generated project's root, update all three top-level extensions with:

```bash
quarto update extension --all
```

Updating `fs-ise-presentation` also updates its embedded Simplemenu dependency;
Simplemenu is deliberately not managed as a separate top-level extension.

Update generated support files from this Copier template with:

```bash
copier update --trust
```

Copier stores the template source and answers in `.copier-answers.yml` and
merges scaffold changes with local changes. In addition, `presentation.qmd` is
marked to be skipped on updates so scaffold refreshes do not overwrite slide
content. Review and commit update results as usual. The generated Makefile
provides the equivalent `make update-extension` and `make update-template`
shortcuts. QRcode and Iconify are Copier-only additions. Both `quarto use
template` and `quarto add` install the FS extension together with its embedded
Simplemenu dependency and do not require Copier.
