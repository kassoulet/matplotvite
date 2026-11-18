//! Figure rendering pipeline, independent of the Python bindings.

use crate::export::{
    background_pixel, content_bbox, crop_pixmap, encode_eps, encode_png, encode_webp,
    figure_background, rasterize, render_pdf, render_svg, svg_tight, FigureDecorations,
    RenderOutput,
};
use crate::fonts::register_plotters_fonts;
use crate::model::{Panel, PngCompression, RenderOptions, Suptitle};
use crate::raster::{direct_eligible, render_png};

/// Why a figure could not be rendered.
#[derive(Debug)]
pub(crate) enum RenderError {
    /// A caller-supplied dimension, format or compression was invalid.
    InvalidSize(String),
    UnsupportedFormat(String),
    InvalidCompression(String),
    CompressionWithoutPng,
    /// Drawing, rasterising or encoding failed.
    Render(String),
}

impl RenderError {
    pub(crate) fn is_value_error(&self) -> bool {
        !matches!(self, Self::Render(_))
    }

    pub(crate) fn into_message(self) -> String {
        match self {
            Self::InvalidSize(message)
            | Self::UnsupportedFormat(message)
            | Self::InvalidCompression(message)
            | Self::Render(message) => message,
            Self::CompressionWithoutPng => {
                "compression is only supported for PNG output".to_string()
            }
        }
    }
}

impl From<String> for RenderError {
    fn from(message: String) -> Self {
        Self::Render(message)
    }
}

/// Render a figure and return its encoded bytes.
///
/// The Python layer owns path handling and format inference; this function only
/// validates its inputs, draws, and encodes. `tight` crops to drawn content.
pub(crate) fn render_figure(
    size: (u32, u32),
    grid: (usize, usize),
    panels: &[Panel],
    options: RenderOptions,
) -> Result<Vec<u8>, RenderError> {
    let RenderOptions {
        format,
        transparent,
        tight,
        dpi,
        facecolor,
        edgecolor,
        compression,
        suptitle,
        suptitle_family,
        suptitle_size,
        suptitle_x,
        suptitle_y,
        figure_texts,
        figure_images,
    } = options;
    register_plotters_fonts();
    let (w, h) = size;
    // Defend against integer overflow and unconstrained allocations (DoS)
    const MAX_CANVAS_DIM: u32 = 32768;
    const MAX_CANVAS_AREA: u64 = 67_108_864; // 2^26 px (~256 MiB RGBA)
    if w == 0 || h == 0 {
        return Err(RenderError::InvalidSize(
            "size dimensions must be at least 1x1".to_string(),
        ));
    }
    if w > MAX_CANVAS_DIM || h > MAX_CANVAS_DIM {
        return Err(RenderError::InvalidSize(format!(
            "size {w}x{h} exceeds maximum dimension of {MAX_CANVAS_DIM}px"
        )));
    }
    if (w as u64) * (h as u64) > MAX_CANVAS_AREA {
        return Err(RenderError::InvalidSize(format!(
            "total canvas area of {w}x{h} exceeds maximum allowed pixel count of {MAX_CANVAS_AREA}"
        )));
    }
    if !dpi.is_finite() || dpi <= 0.0 {
        return Err(RenderError::InvalidSize(
            "dpi must be positive and finite".to_string(),
        ));
    }
    let fmt = format.to_ascii_lowercase();
    if !matches!(fmt.as_str(), "png" | "svg" | "pdf" | "webp" | "eps") {
        return Err(RenderError::UnsupportedFormat(format!(
            "unsupported format: {format:?} (use 'png', 'svg', 'pdf', 'webp', or 'eps')"
        )));
    }
    let compression = match compression {
        Some(value) => Some(PngCompression::parse(&value).ok_or_else(|| {
            RenderError::InvalidCompression(format!(
                "unsupported compression: {value:?} (use 'fast', 'default', or 'best')"
            ))
        })?),
        None => None,
    };
    if compression.is_some() && fmt != "png" {
        return Err(RenderError::CompressionWithoutPng);
    }

    let background = figure_background(transparent, facecolor.map(|c| c.rgba()));
    let title = (!suptitle.is_empty()).then_some(Suptitle {
        text: &suptitle,
        family: &suptitle_family,
        size: suptitle_size,
        x: suptitle_x,
        y: suptitle_y,
    });
    let decorations = FigureDecorations {
        suptitle: title,
        texts: &figure_texts,
        edgecolor: edgecolor.map(|c| c.rgba()),
    };
    let output = RenderOutput {
        dpi,
        raster: matches!(fmt.as_str(), "png" | "webp" | "eps"),
        // PDF measures its own bounds while embedding the SVG, so only SVG
        // needs the extra usvg pass here.
        tight_bounds: tight && fmt == "svg",
    };

    // The direct bitmap path skips SVG generation and resvg. It currently
    // covers opaque PNGs without embedded images or figure decorations; the
    // vector path remains the fallback for everything else.
    let direct = fmt == "png"
        && !transparent
        && decorations.is_empty()
        && figure_images.is_empty()
        && direct_eligible(panels);
    let direct_background =
        background_pixel(background).map(|pixel| [pixel[0], pixel[1], pixel[2]]);

    if direct {
        let background = direct_background.ok_or_else(|| {
            RenderError::Render("direct PNG requires an opaque background".into())
        })?;
        let pixmap = render_png(size, grid, panels, background)?;
        let pixmap = match if tight {
            content_bbox(
                &pixmap,
                Some([background[0], background[1], background[2], 255]),
            )
        } else {
            None
        } {
            Some(bbox) => crop_pixmap(&pixmap, bbox)?,
            None => pixmap,
        };
        return encode_png(&pixmap, compression.unwrap_or(PngCompression::Fast), true)
            .map_err(|e| RenderError::Render(e.to_string()));
    }
    // PDF receives an unbacked SVG so its single parse can measure the
    // drawn content; it paints the background onto the cropped page.
    let svg_background = if fmt == "pdf" { None } else { background };
    let (svg, bounds) = render_svg(
        size,
        grid,
        panels,
        &figure_images,
        svg_background,
        decorations,
        output,
    )?;
    if fmt == "pdf" {
        render_pdf(&svg, dpi, size, tight, background).map_err(RenderError::Render)
    } else if fmt == "svg" {
        let svg = match if tight {
            bounds.and_then(|bbox| svg_tight(&svg, bbox))
        } else {
            None
        } {
            Some(svg) => svg,
            None => svg,
        };
        Ok(svg.into_bytes())
    } else {
        let pixmap = rasterize(&svg, w, h, transparent)?;
        let pixmap = match if tight {
            content_bbox(&pixmap, background_pixel(background))
        } else {
            None
        } {
            Some(bbox) => crop_pixmap(&pixmap, bbox)?,
            None => pixmap,
        };
        if fmt == "eps" {
            Ok(encode_eps(&pixmap, dpi))
        } else if fmt == "webp" {
            encode_webp(&pixmap).map_err(RenderError::Render)
        } else {
            encode_png(
                &pixmap,
                compression.unwrap_or(PngCompression::Fast),
                !transparent,
            )
            .map_err(|e| RenderError::Render(e.to_string()))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::color::Color;
    use crate::fonts::SANS_FAMILY;
    use crate::model::{DrawStyle, LineStyle, Panel, RenderOptions, Series};

    fn smoke_panel() -> Panel {
        Panel {
            dpi: 100.0,
            font_family: SANS_FAMILY.to_string(),
            title: "Smoke".to_string(),
            xlabel: "x".to_string(),
            ylabel: "y".to_string(),
            title_size: Some(12.0),
            xlabel_size: Some(10.0),
            ylabel_size: Some(10.0),
            series: vec![Series {
                x: vec![0.0, 1.0, 2.0].into(),
                y: vec![0.0, 1.0, 0.0].into(),
                label: "line".to_string(),
                color: Color::parse("#1f77b4"),
                linestyle: LineStyle::Solid,
                linewidth: 1.5,
                markersize: 6.0,
                mew: 1.0,
                drawstyle: DrawStyle::default(),
                ..Default::default()
            }],
            ..Default::default()
        }
    }

    fn smoke_options(format: &str) -> RenderOptions {
        RenderOptions {
            format: format.to_string(),
            dpi: 100.0,
            ..Default::default()
        }
    }

    #[test]
    fn renders_a_line_to_png_without_python() {
        let png = render_figure((320, 240), (1, 1), &[smoke_panel()], smoke_options("png"))
            .expect("minimal line figure renders");
        assert!(png.starts_with(b"\x89PNG\r\n\x1a\n"));
    }

    #[test]
    fn renders_a_line_to_svg_without_python() {
        let svg = render_figure((320, 240), (1, 1), &[smoke_panel()], smoke_options("svg"))
            .expect("minimal line figure renders");
        let text = String::from_utf8(svg).expect("SVG is UTF-8");
        assert!(text.starts_with("<svg"));
        assert!(text.contains("Smoke"));
    }

    #[test]
    fn only_render_failures_are_not_value_errors() {
        assert!(RenderError::InvalidSize(String::new()).is_value_error());
        assert!(RenderError::UnsupportedFormat(String::new()).is_value_error());
        assert!(RenderError::InvalidCompression(String::new()).is_value_error());
        assert!(RenderError::CompressionWithoutPng.is_value_error());
        assert!(!RenderError::Render(String::new()).is_value_error());
    }
}
