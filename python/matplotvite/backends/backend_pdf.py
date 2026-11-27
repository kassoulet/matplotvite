"""Minimal ``PdfPages``: several figures in one multi-page PDF."""

import os
from typing import Any

from .._core import render_pdf_pages as _render_pdf_pages

__all__ = ("PdfPages",)


class PdfPages:
    """Collect figures and write them as pages of one PDF document.

    Each ``savefig`` renders its figure to SVG and keeps the page in memory;
    ``close`` (or leaving the context manager) assembles the document.
    Metadata and annotations are accepted but only ``infodict`` stores them.
    """

    def __init__(self, filename: Any, keep_empty: Any = True, metadata: Any = None) -> None:
        self._filename = filename
        self._keep_empty = bool(keep_empty)
        self._metadata = dict(metadata or {})
        self._pages: list[Any] = []

    def savefig(self, figure: Any = None, **kwargs: Any) -> Any:
        from matplotvite import gcf

        fig = gcf() if figure is None else figure
        dpi = float(kwargs.pop("dpi", None) or fig.get_dpi())
        kwargs.pop("format", None)
        kwargs.pop("metadata", None)
        svg = fig.savefig(None, format="svg", dpi=dpi, **kwargs)
        self._pages.append((svg, dpi))

    def close(self) -> Any:
        if not self._pages:
            return
        data = _render_pdf_pages(
            [page for page, _ in self._pages],
            [dpi for _, dpi in self._pages],
        )
        if hasattr(self._filename, "write"):
            self._filename.write(data)
        else:
            with open(os.fspath(self._filename), "wb") as handle:
                handle.write(data)
        self._pages = []

    def infodict(self) -> Any:
        """The metadata mapping passed to the constructor."""
        return self._metadata

    def attach_note(self, text: Any, position: Any = None) -> Any:
        """Accepted for compatibility; notes are not written into the PDF."""
        return None

    def get_pagecount(self) -> Any:
        return len(self._pages)

    def __enter__(self) -> Any:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> Any:
        self.close()
