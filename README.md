# FS-ISE Presentation Template

A reusable Quarto/reveal.js presentation template with Frankfurt School branding, slide numbering, and Simplemenu navigation.

[![FS-ISE Presentation Preview](https://fs-ise.github.io/quarto-template-presentation/preview.png)](https://fs-ise.github.io/quarto-template-presentation/)

Click the preview to open the interactive presentation.

## Create a presentation with Copier

Create a new presentation project:

```
copier copy --trust gh:fs-ise/quarto-template-presentation my-presentation
cd my-presentation
```

Copier prompts for the presentation title, author, and optional subtitle. The required Quarto extensions are installed automatically.

## Alternatively: Install the Quarto extension

To add the presentation format to an existing Quarto project:

```
quarto add fs-ise/quarto-template-presentation
```

Use `format: fs-ise-presentation-revealjs` in the document's YAML metadata.
Simplemenu is included in the extension and pinned to upstream v2.0.1
(`6fa39e6aca0ec8762d463c50ebf4fda92ad997da`); its JavaScript and CSS are
unmodified.

## Section navigation

Flat navigation is enabled by default. Make each section label a level-2
content slide with `data-name`; later level-2 slides inherit that label until
the next named slide. There are no separate section-divider slides:

```markdown
## Introduction {data-name="Introduction"}
Your first content slide.

## Supporting evidence
This slide is also part of Introduction.

## Recommendations {data-name="Recommendations"}
This starts the next navigation section.
```

The FS-ISE format sets `section-divs: false` for this flat structure. To use
Reveal vertical stacks in a document, set both options explicitly and structure
the headings as level-1 stacks with level-2 slides. Put `data-stack-name` on the
first level-2 slide of each stack:

```yaml
format:
  fs-ise-presentation-revealjs:
    section-divs: true
    simplemenu:
      flat: false
```

```markdown
# Introduction
## First content slide {data-stack-name="Introduction"}
## Another slide in this stack
```

## Render

From a Copier-generated project:

```
quarto render
```

For an interactive preview:

```
quarto preview presentation.qmd
```

## Customize the closing slide

Edit the final `Let’s discuss` slide directly in `presentation.qmd` in a
Copier-generated project, or `template.qmd` for this repository's example.
The top two columns contain one quoted example takeaway and the discussion
prompt, with a larger QR code under the plain **Explore the research** heading.
Advance once to reveal the thank-you message and all three presenter cards
together with the Explore heading and QR code. Links and quote rules use the
Frankfurt blue accent. Edit each card's Markdown name, affiliation, visible
email, and profile links directly; remove or duplicate a `.column` to change
the presenter count. The repository's offline QR asset encodes
`https://example.com`; update the asset as well if you change the shortcode
destination.

To render this repository's example presentation:

```
quarto render template.qmd
```

## Development

To preview changes run

```
quarto render template.qmd
quarto preview template.qmd
```

## Update a Copier project

To update the generated project from the latest template:

```
copier update --trust
```

Copier retains your answers in `.copier-answers.yml` and protects `presentation.qmd` from template updates.
