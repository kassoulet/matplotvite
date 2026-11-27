"""PNG decoding and encoding plus image file I/O."""
import os
import struct as _struct
import zlib as _zlib
from typing import Any, Callable, NoReturn, Optional

import numpy as np

from ._config import rcParams
from ._figure import Figure
from ._helpers import _FORMATS, get_cmap
from ._ticker import _PNG_SIGNATURE


def _png_unfilter_serial(row: np.ndarray, previous: np.ndarray, bpp: int,
                         filter_type: int) -> None:
    """Undo PNG filter 3 (average) or 4 (Paeth) in place; both depend on the left byte."""
    cur, up = row.tolist(), previous.tolist()
    for i in range(len(cur)):
        left = cur[i - bpp] if i >= bpp else 0
        above = up[i]
        if filter_type == 3:
            predictor = (left + above) // 2
        else:
            upper_left = up[i - bpp] if i >= bpp else 0
            p = left + above - upper_left
            pa, pb, pc = abs(p - left), abs(p - above), abs(p - upper_left)
            predictor = left if pa <= pb and pa <= pc else above if pb <= pc else upper_left
        cur[i] = (cur[i] + predictor) & 255
    row[:] = cur


_PNG_MAX_BYTES = 1 << 29  # 512 MiB of inflated scanlines


def _decode_png(data: bytes) -> np.ndarray:
    """Decode a non-interlaced PNG into a float array in the range 0-1.

    Matplotlib's image tests use every PNG colour type and bit depth, while
    matplotvite deliberately has no Pillow dependency. This decoder covers the
    standard non-interlaced grayscale, palette, RGB and alpha variants.
    """
    if data[:8] != _PNG_SIGNATURE:
        raise ValueError("not a PNG file")
    width: Optional[int] = None
    height: Optional[int] = None
    depth: Optional[int] = None
    color: Optional[int] = None
    interlace: Optional[int] = None
    palette: Optional[bytes] = None
    transparency: Optional[bytes] = None
    compressed = bytearray()
    pos = 8
    while pos + 12 <= len(data):
        length = int.from_bytes(data[pos:pos + 4], "big")
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            if len(body) < 13:
                raise ValueError("truncated PNG IHDR chunk")
            width, height, depth, color, compression, filter_method, interlace = \
                _struct.unpack(">IIBBBBB", body[:13])
            if compression != 0 or filter_method != 0:
                raise ValueError("unsupported PNG compression or filter method")
        elif kind == b"PLTE":
            palette = body
        elif kind == b"tRNS":
            transparency = body
        elif kind == b"IDAT":
            compressed.extend(body)
        elif kind == b"IEND":
            break
    if width is None or height is None:
        raise ValueError("PNG has no IHDR chunk")
    if interlace:
        raise NotImplementedError("interlaced PNG files are not supported")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color)  # type: ignore[arg-type]
    if channels is None:
        raise ValueError(f"unsupported PNG colour type {color}")
    if depth is None or depth not in (1, 2, 4, 8, 16) \
            or (depth < 8 and color not in (0, 3)):
        raise ValueError(f"unsupported PNG bit depth {depth}")
    if color == 3 and palette is None:
        raise ValueError("palette PNG has no PLTE chunk")
    bits_per_pixel = channels * depth
    stride = (width * bits_per_pixel + 7) // 8
    bpp = max(1, (bits_per_pixel + 7) // 8)
    # Cap the inflated size at what the header promises, so a small crafted
    # file cannot expand into gigabytes (decompression bomb).
    expected = height * (stride + 1)
    if expected > _PNG_MAX_BYTES:
        raise ValueError("PNG image is too large to decode")
    try:
        inflater = _zlib.decompressobj()
        raw = inflater.decompress(bytes(compressed), expected + 1)
    except _zlib.error as exc:
        raise ValueError(f"corrupt PNG image data: {exc}") from exc
    if inflater.unconsumed_tail or len(raw) > expected:
        raise ValueError("PNG image data is larger than its header declares")
    if len(raw) < height * (stride + 1):
        raise ValueError("truncated PNG image data")
    lines = np.frombuffer(raw, dtype=np.uint8, count=expected).reshape(height, stride + 1)
    pixels = lines[:, 1:].copy()
    previous = np.zeros(stride, dtype=np.uint8)
    for y in range(height):
        filter_type = int(lines[y, 0])
        row = pixels[y]
        if filter_type == 1:
            row[:] = row.reshape(-1, bpp).cumsum(axis=0, dtype=np.uint64).astype(
                np.uint8).reshape(-1)
        elif filter_type == 2:
            row += previous
        elif filter_type in (3, 4):
            _png_unfilter_serial(row, previous, bpp, filter_type)
        elif filter_type != 0:
            raise ValueError(f"unsupported PNG filter type {filter_type}")
        previous = row

    count = width * channels
    if depth == 8:
        samples = pixels[:, :count]
    elif depth == 16:
        samples = np.ascontiguousarray(pixels[:, :count * 2]).view(">u2")
    else:
        bits = np.unpackbits(pixels, axis=1).reshape(height, -1, depth)
        samples = (bits * (1 << np.arange(depth - 1, -1, -1))).sum(axis=2)[:, :count]
    scale = (float((1 << depth) - 1) if color == 0 and depth < 8
             else 255.0 if depth <= 8 else 65535.0)
    if color == 3:
        entries = np.frombuffer(bytes(palette[:len(palette) // 3 * 3]),  # type: ignore[arg-type,index]
                                dtype=np.uint8).reshape(-1, 3)
        if samples.size and int(samples.max()) >= len(entries):
            raise ValueError("PNG palette index out of range")
        alpha = np.full(len(entries), 255, dtype=np.uint8)
        if transparency:
            keep = min(len(transparency), len(entries))
            alpha[:keep] = np.frombuffer(bytes(transparency[:keep]), dtype=np.uint8)
        rgb = entries[samples].astype(np.float64) / 255.0
        if (alpha != 255).any():
            return np.concatenate(
                [rgb, (alpha[samples].astype(np.float64) / 255.0)[..., None]], axis=2)
        return rgb

    array = np.asarray(samples, dtype=np.float64) / scale
    if color == 0:
        return array.reshape(height, width)
    image = array.reshape(height, width, channels)
    if color == 4:
        gray = image[..., 0:1]
        return np.concatenate([np.repeat(gray, 3, axis=2), image[..., 1:2]], axis=2)
    if color == 2 and transparency and len(transparency) == 6:
        key = np.asarray(_struct.unpack(">HHH", transparency), dtype=np.float64) / scale
        mask = np.all(image == key, axis=2)
        return np.concatenate([image, (~mask)[..., None].astype(np.float64)], axis=2)
    return image


def _write_png_image(fname: Any, rgba: Any) -> None:
    """Write an HxW(x1/2/3/4) uint8 image as PNG without Pillow."""
    rgba = np.ascontiguousarray(np.asarray(rgba, dtype=np.uint8))
    if rgba.ndim == 2:
        rgba = rgba[:, :, None]
    if rgba.ndim != 3 or rgba.shape[2] not in (1, 2, 3, 4):
        raise ValueError("PNG image must be HxW or HxWx1/2/3/4")
    height, width = rgba.shape[:2]
    color_type = {1: 0, 2: 4, 3: 2, 4: 6}[rgba.shape[2]]
    raw = b"".join(b"\x00" + rgba[row].tobytes() for row in range(height))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        crc = _zlib.crc32(tag + payload) & 0xFFFFFFFF
        return (_struct.pack(">I", len(payload)) + tag + payload
                + _struct.pack(">I", crc))

    png = (_PNG_SIGNATURE
           + chunk(b"IHDR", _struct.pack(">IIBBBBB", width, height, 8,
                                          color_type, 0, 0, 0))
           + chunk(b"IDAT", _zlib.compress(raw))
           + chunk(b"IEND", b""))
    if hasattr(fname, "write"):
        fname.write(png)
        return
    with open(os.fspath(fname), "wb") as stream:
        stream.write(png)


def imsave(fname: Any, arr: Any, vmin: Optional[float] = None,
           vmax: Optional[float] = None, cmap: Any = None,
           format: Optional[str] = None, origin: Optional[str] = None,
           dpi: float = 100, *, metadata: Any = None,
           pil_kwargs: Optional[dict[str, Any]] = None) -> None:
    """Save an array as an image file, as `matplotlib.pyplot.imsave`.

    A 2-D array is mapped through `cmap`; an HxWx3/HxWx4 array is written as
    colour. PNG is encoded natively, other formats go through Pillow (and
    vector formats through the renderer).
    """
    data = np.asarray(arr)
    if data.ndim == 2:
        lo = float(vmin) if vmin is not None else None
        hi = float(vmax) if vmax is not None else None
        if lo is None or hi is None:
            finite = data[np.isfinite(data)]
            lo = float(finite.min()) if lo is None and finite.size else lo
            hi = float(finite.max()) if hi is None and finite.size else hi
        if lo is None or hi is None or not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            lo, hi = 0.0, 1.0
        normalized = np.clip((data - lo) / (hi - lo), 0.0, 1.0)
        name = cmap if cmap is not None else rcParams.get("image.cmap", "viridis")
        rgba = np.asarray(get_cmap(name)(normalized), dtype=float)
        rgba = np.clip(rgba * 255.0, 0.0, 255.0).astype(np.uint8)
    elif data.ndim == 3 and data.shape[2] in (3, 4):
        rgba = (data if data.dtype == np.uint8 else
                np.clip(np.asarray(data, dtype=float) * 255.0, 0.0, 255.0).astype(np.uint8))
    else:
        raise ValueError("imsave expects a 2-D array or an HxWx3/HxWx4 array")
    if origin == "lower":
        rgba = rgba[::-1]
    height, width = rgba.shape[:2]

    if format is None:
        name = (fname if isinstance(fname, (str, bytes, os.PathLike))
                else getattr(fname, "name", ""))
        fmt = os.path.splitext(os.fsdecode(name))[1].lower().lstrip(".") or "png"
    else:
        fmt = str(format).lower().lstrip(".")
    fmt = {"jpeg": "jpg", "tif": "tiff", "ps": "eps"}.get(fmt, fmt)

    if fmt == "png" and not pil_kwargs and metadata is None:
        _write_png_image(fname, rgba)
        return
    if fmt in ("png", "jpg", "tiff"):
        try:
            from PIL import Image
        except ImportError as exc:
            raise ImportError(
                "this imsave format needs Pillow; PNG is the only native format"
            ) from exc
        image = Image.fromarray(rgba)
        if fmt == "jpg":
            image = image.convert("RGB")
        kwargs = dict(pil_kwargs or {})
        kwargs.setdefault("format", {"png": "PNG", "jpg": "JPEG",
                                     "tiff": "TIFF"}[fmt])
        if dpi is not None:
            kwargs.setdefault("dpi", (float(dpi), float(dpi)))
        image.save(fname, **kwargs)
        return
    if fmt not in _FORMATS:
        raise ValueError(f"unsupported format: {fmt!r}")
    fig = Figure(figsize=(max(width, 1) / float(dpi or 100),
                          max(height, 1) / float(dpi or 100)),
                 dpi=dpi or 100)
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.imshow(rgba, aspect="auto", interpolation="nearest", origin="upper")
    ax.set_axis_off()
    fig.savefig(fname, format=fmt, dpi=dpi or 100)


def _imread(fname: Any, format: Optional[str] = None) -> np.ndarray:
    """Read a PNG natively, or another image format through Pillow."""
    if hasattr(fname, "read"):
        data = fname.read()
    else:
        with open(os.fspath(fname), "rb") as stream:
            data = stream.read()
    if isinstance(data, str):
        data = data.encode("latin-1")
    if (format is None or str(format).lower() == "png") and data.startswith(_PNG_SIGNATURE):
        return _decode_png(data)
    try:
        import io

        from PIL import Image
    except ImportError as exc:
        raise ImportError(
            "matplotvite.imread supports PNG without Pillow; other formats need Pillow"
        ) from exc
    with Image.open(io.BytesIO(data), formats=None if format is None else [format]) as image:
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            return np.asarray(image.convert("RGBA"), dtype=np.float64) / 255.0
        return np.asarray(image.convert("RGB"), dtype=np.float64) / 255.0


imread = _imread


def _get_sample_data(name: str, asfileobj: bool = True) -> NoReturn:
    """Matplotlib's sample-data directory is not shipped with matplotvite."""
    raise FileNotFoundError(
        f"matplotvite does not bundle Matplotlib's sample data ({name!r})")


def _flatten(seq: Any, scalarp: Optional[Callable[[Any], bool]] = None) -> list[Any]:
    """Depth-first flatten of nested sequences, as `cbook.flatten`."""
    if scalarp is None:
        scalarp = lambda value: not hasattr(value, "__iter__") or isinstance(value, str)
    if scalarp(seq):
        return [seq]
    out = []
    for item in seq:
        out.extend(_flatten(item, scalarp))
    return out
