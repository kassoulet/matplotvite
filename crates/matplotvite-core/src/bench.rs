//! Hidden hooks used by the Criterion benchmark target.
//!
//! These wrappers expose only the output stages that do not require a Python
//! interpreter, keeping the benchmark executable independent of the extension
//! module's GIL and NumPy array types.

use crate::export::{encode_png, encode_webp, rasterize, render_pdf};
use crate::model::PngCompression;

/// Rasterize SVG markup at the requested pixel size.
pub fn rasterize_svg(svg: &str, width: u32, height: u32) -> Result<(), String> {
    rasterize(svg, width, height, false).map(|_| ())
}

/// Encode a pixmap as PNG at the requested compression level.
pub fn encode_png_bytes(
    pixmap: &tiny_skia::Pixmap,
    compression: &str,
    opaque: bool,
) -> Result<Vec<u8>, String> {
    let compression = PngCompression::parse(compression)
        .ok_or_else(|| format!("unsupported compression: {compression:?}"))?;
    encode_png(pixmap, compression, opaque).map_err(|error| error.to_string())
}

/// Encode a pixmap as lossless WebP.
pub fn encode_webp_bytes(pixmap: &tiny_skia::Pixmap) -> Result<Vec<u8>, String> {
    encode_webp(pixmap)
}

/// Convert SVG markup into a vector PDF.
pub fn svg_to_pdf(svg: &str, dpi: f64, size: (u32, u32), tight: bool) -> Result<Vec<u8>, String> {
    render_pdf(svg, dpi, size, tight, None)
}
