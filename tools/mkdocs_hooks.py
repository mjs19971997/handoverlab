# SPDX-License-Identifier: MIT
"""MkDocs hook: tidy the reStructuredText roles of the docstrings in the generated API pages.

The docstrings use roles such as :func:`name` and :class:`~handoverlab.simulate.RunResult`;
Markdown renders the name as code and leaves the role text in front of it.  This hook removes
the role text and shortens ``~package.module.Name`` to ``Name``.
"""
import re

_ROLE = re.compile(r":(?:data|func|class|mod|meth|attr|exc|obj):(\s*<code>)")
_TILDE = re.compile(r"<code>~(?:[A-Za-z_][\w]*\.)*([A-Za-z_][\w]*)</code>")
_LITERAL = re.compile(r"``([^`<>\n]+)``")
_RAW = re.compile(r":(?:data|func|class|mod|meth|attr|exc|obj):`(~?)([^`<>\n]+)`")


def _raw(m):
    return m.group(2).rsplit(".", 1)[-1] if m.group(1) else m.group(2)


def on_page_content(html, page, config, files):
    if not page.file.src_uri.startswith("reference/api/"):
        return html
    html = _ROLE.sub(r"\1", html)
    html = _TILDE.sub(r"<code>\1</code>", html)
    html = _LITERAL.sub(r"\1", html)
    return _RAW.sub(_raw, html)
