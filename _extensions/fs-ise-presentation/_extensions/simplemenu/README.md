# Simplemenu

This directory embeds the
[`quarto-simplemenu`](https://github.com/martinomagnifico/quarto-simplemenu)
Reveal.js plugin by Martin Donath as a Quarto embedded extension. It is
distributed under the MIT license in `LICENSE`.

Keeping the plugin below the parent extension's `_extensions` directory is
Quarto's supported mechanism for shipping an extension dependency. Do not
move it to the repository-level `_extensions` directory or install it as a
separate Copier task.

The JavaScript retains upstream Simplemenu's stack discovery behaviour, which
accepts `data-stack-name` on either a horizontal section or one of its direct
vertical children. The local stylesheet and footer markup adapt the plugin to
the FS-ISE navigation design and accessible slide-number display.
