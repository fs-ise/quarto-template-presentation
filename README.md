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

Use `format: fs-ise-presentation-revealjs` in the document's YAML metadata. Simplemenu is included in the extension.

## Render

From a Copier-generated project:

```
quarto render
```

For an interactive preview:

```
quarto preview presentation.qmd
```

To render this repository's example presentation:

```
quarto render template.qmd
```

## Update a Copier project

To update the generated project from the latest template:

```
copier update --trust
```

Copier retains your answers in `.copier-answers.yml` and protects `presentation.qmd` from template updates.
