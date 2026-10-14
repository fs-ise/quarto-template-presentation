# Embedded Simplemenu

This directory vendors the official
[`quarto-simplemenu`](https://github.com/Martinomagnifico/quarto-simplemenu)
Quarto extension, release **v2.0.1**, commit
[`6fa39e6aca0ec8762d463c50ebf4fda92ad997da`](https://github.com/Martinomagnifico/quarto-simplemenu/commit/6fa39e6aca0ec8762d463c50ebf4fda92ad997da).
The upstream JavaScript and CSS are copied byte-for-byte from that revision.
The upstream extension manifest reports version 2.0.0 in this release.

The MIT license applies; see `LICENSE`. The parent FS-ISE extension configures
flat navigation and the footer markup, while its `custom.scss` supplies the
FS-ISE presentation styling. Keep those customizations outside the upstream
JavaScript and CSS.

Keep this extension nested below `fs-ise-presentation/_extensions/` so Quarto
ships it with the FS-ISE format and users do not need to install it separately.
