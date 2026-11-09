mod cmap_data;
mod color;
mod draw;
mod export;
mod fonts;
mod image;
mod layout;
mod model;

#[doc(hidden)]
pub mod bench;

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;

use crate::export::{
    background_pixel, content_bbox, crop_pixmap, encode_png, encode_webp, figure_background,
    rasterize, render_pdf, render_svg, svg_tight, RenderOutput,
};
use crate::fonts::register_plotters_fonts;
use crate::model::{Panel, PngCompression, RenderOptions, Suptitle};

/// Render a figure and return its encoded bytes.
///
/// The Python layer owns path handling and format inference; this function only
/// validates its inputs, draws, and encodes. `tight` crops to drawn content.
#[pyfunction]
#[pyo3(signature = (size, grid, panels, options))]
fn render(
    size: (u32, u32),
    grid: (usize, usize),
    panels: Vec<Panel>,
    options: RenderOptions,
) -> PyResult<Vec<u8>> {
    let RenderOptions {
        format,
        transparent,
        tight,
        dpi,
        facecolor,
        edgecolor,
        compression,
        suptitle,
        suptitle_size,
        suptitle_x,
        suptitle_y,
    } = options;
    let err = |e: &str| PyRuntimeError::new_err(e.to_string());
    register_plotters_fonts();
    if suptitle.is_empty()
        && panels.iter().all(|p| {
            p.series.is_empty()
                && p.texts.is_empty()
                && p.images.is_empty()
                && p.annotations.is_empty()
                && p.contours.is_empty()
                && p.errors.is_empty()
                && p.scatter.is_empty()
                && p.arrows.is_empty()
                && p.bars.is_empty()
                && p.bands.is_empty()
                && p.patches.is_empty()
                && p.collections.is_empty()
                && p.colorbar.is_none()
        })
    {
        return Err(PyRuntimeError::new_err("nothing to plot"));
    }
    let (w, h) = size;
    // Defend against integer overflow and unconstrained allocations (DoS)
    const MAX_CANVAS_DIM: u32 = 32768;
    const MAX_CANVAS_AREA: u64 = 268435456; // 2^28 px
    if w == 0 || h == 0 {
        return Err(PyValueError::new_err(
            "size dimensions must be at least 1x1",
        ));
    }
    if w > MAX_CANVAS_DIM || h > MAX_CANVAS_DIM {
        return Err(PyValueError::new_err(format!(
            "size {w}x{h} exceeds maximum dimension of {MAX_CANVAS_DIM}px"
        )));
    }
    if (w as u64) * (h as u64) > MAX_CANVAS_AREA {
        return Err(PyValueError::new_err(format!(
            "total canvas area of {w}x{h} exceeds maximum allowed pixel count of {MAX_CANVAS_AREA}"
        )));
    }
    if !dpi.is_finite() || dpi <= 0.0 {
        return Err(PyValueError::new_err("dpi must be positive and finite"));
    }
    let fmt = format.to_ascii_lowercase();
    if !matches!(fmt.as_str(), "png" | "svg" | "pdf" | "webp") {
        return Err(PyValueError::new_err(format!(
            "unsupported format: {format:?} (use 'png', 'svg', 'pdf', or 'webp')"
        )));
    }
    let compression = match compression {
        Some(value) => Some(PngCompression::parse(&value).ok_or_else(|| {
            PyValueError::new_err(format!(
                "unsupported compression: {value:?} (use 'fast', 'default', or 'best')"
            ))
        })?),
        None => None,
    };
    if compression.is_some() && fmt != "png" {
        return Err(PyValueError::new_err(
            "compression is only supported for PNG output",
        ));
    }

    let background = figure_background(transparent, facecolor.as_deref());
    let title = (!suptitle.is_empty()).then_some(Suptitle {
        text: &suptitle,
        size: suptitle_size,
        x: suptitle_x,
        y: suptitle_y,
    });
    let svg = render_svg(
        size,
        grid,
        &panels,
        background,
        edgecolor.as_deref(),
        title,
        RenderOutput {
            dpi,
            raster: matches!(fmt.as_str(), "png" | "webp"),
        },
    )
    .map_err(|e| err(&e))?;
    if fmt == "svg" || fmt == "pdf" {
        let svg = match if tight {
            rasterize(&svg, w, h, transparent)
                .ok()
                .and_then(|p| content_bbox(&p, background_pixel(background)))
                .and_then(|bbox| svg_tight(&svg, bbox))
        } else {
            None
        } {
            Some(svg) => svg,
            None => svg,
        };
        if fmt == "pdf" {
            render_pdf(&svg, dpi).map_err(|e| err(&e))
        } else {
            Ok(svg.into_bytes())
        }
    } else {
        let pixmap = rasterize(&svg, w, h, transparent).map_err(|e| err(&e))?;
        let pixmap = match if tight {
            content_bbox(&pixmap, background_pixel(background))
        } else {
            None
        } {
            Some(bbox) => crop_pixmap(&pixmap, bbox).map_err(|e| err(&e))?,
            None => pixmap,
        };
        if fmt == "webp" {
            encode_webp(&pixmap).map_err(|e| err(&e))
        } else {
            encode_png(
                &pixmap,
                compression.unwrap_or(PngCompression::Fast),
                !transparent,
            )
            .map_err(|e| err(&e.to_string()))
        }
    }
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(render, m)?)
}

#[cfg(test)]
mod tests {
    use super::*;
    use plotters::prelude::RGBAColor;

    use crate::layout::range;

    fn decode_png(bytes: &[u8]) -> (u32, u32, Vec<u8>) {
        let decoder = png::Decoder::new(std::io::Cursor::new(bytes));
        let mut reader = decoder.read_info().unwrap();
        let mut buf = vec![0; reader.output_buffer_size().expect("valid PNG buffer size")];
        let info = reader.next_frame(&mut buf).unwrap();
        buf.truncate(info.buffer_size());
        (info.width, info.height, buf)
    }

    #[test]
    fn panels_can_be_shared_between_render_threads() {
        fn assert_sync<T: Sync>() {}
        assert_sync::<Panel<'static>>();
    }

    #[test]
    fn range_ignores_non_finite_values() {
        assert_eq!(
            range([f64::NAN, 2.0, f64::INFINITY].into_iter()),
            (1.0, 3.0)
        );
        assert_eq!(range([f64::NAN, f64::INFINITY].into_iter()), (0.0, 1.0));
    }

    #[test]
    fn content_bbox_uses_the_figure_background() {
        let mut pixmap = tiny_skia::Pixmap::new(3, 3).unwrap();
        pixmap.fill(tiny_skia::Color::from_rgba8(255, 0, 0, 255));
        pixmap.pixels_mut()[4] = tiny_skia::PremultipliedColorU8::from_rgba(0, 0, 0, 255).unwrap();
        let background = background_pixel(Some(RGBAColor(255, 0, 0, 1.0)));
        assert_eq!(content_bbox(&pixmap, background), Some((1, 1, 1, 1)));
    }

    #[test]
    fn png_compression_preserves_transparent_pixels() {
        let mut pixmap = tiny_skia::Pixmap::new(3, 2).unwrap();
        let colors = [
            (0, 0, 0, 0),
            (64, 32, 16, 128),
            (255, 128, 0, 255),
            (10, 20, 30, 64),
            (128, 128, 128, 128),
            (1, 2, 3, 255),
        ];
        for (pixel, &(r, g, b, a)) in pixmap.pixels_mut().iter_mut().zip(&colors) {
            *pixel = tiny_skia::PremultipliedColorU8::from_rgba(r, g, b, a).unwrap();
        }

        let reference = decode_png(&pixmap.encode_png().unwrap());
        for compression in [
            PngCompression::Fast,
            PngCompression::Default,
            PngCompression::Best,
        ] {
            let encoded = encode_png(&pixmap, compression, false).unwrap();
            assert_eq!(decode_png(&encoded), reference);
        }
    }

    #[test]
    fn opaque_png_matches_the_demultiplied_encoding() {
        // Skipping demultiplication is only valid when alpha is 255 everywhere,
        // so the shortcut must be byte-identical to the general path.
        let mut pixmap = tiny_skia::Pixmap::new(8, 8).unwrap();
        for (index, pixel) in pixmap.pixels_mut().iter_mut().enumerate() {
            let channel = (index % 256) as u8;
            *pixel = tiny_skia::PremultipliedColorU8::from_rgba(channel, 17, 240, 255).unwrap();
        }

        for compression in [
            PngCompression::Fast,
            PngCompression::Default,
            PngCompression::Best,
        ] {
            let opaque = encode_png(&pixmap, compression, true).unwrap();
            let demultiplied = encode_png(&pixmap, compression, false).unwrap();
            assert_eq!(opaque, demultiplied);
        }
    }
}
