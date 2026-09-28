.PHONY: install render preview update-extension update-template

install:
	quarto add fs-ise/quarto-template-presentation --no-prompt
	quarto add jmbuhr/quarto-qrcode --no-prompt
	quarto add mcanouil/quarto-iconify --no-prompt

render:
	quarto render

preview:
	quarto preview presentation.qmd

update-extension:
	quarto update extension --all

update-template:
	copier update --trust
