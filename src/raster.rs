//! Direct PNG panel rendering. Panels are drawn by plotters' bitmap backend at
//! an integer oversampling factor, box-filtered down to logical resolution, and
//! composited into one opaque pixmap. This bypasses the SVG document entirely
//! for the common raster path.

use plotters::backend::BitMapBackend;
use plotters::prelude::*;
use rayon::prelude::*;

use crate::draw::draw_panel;
use crate::model::Panel;
use crate::scale::ScaleBackend;

/// Oversampling factor. Two samples per axis gives anti-aliased text and thin
/// strokes at a fraction of the memory and time of 3x/4x.
const OVERSAMPLE: u32 = 2;

/// Match the figure-canvas budget in `lib.rs`.
const MAX_CANVAS_AREA: u64 = 268_435_456;

#[derive(Clone, Copy)]
struct PanelRect {
    x: i32,
    y: i32,
    w: u32,
    h: u32,
}

fn split_evenly(from: i32, to: i32, n: usize, idx: usize) -> i32 {
    let size = (to - from) as usize;
    from + idx as i32 * (size / n) as i32 + idx.min(size % n) as i32
}

/// The logical canvas rectangle that `draw_panel` would occupy in the SVG path.
fn panel_rect(size: (u32, u32), grid: (usize, usize), p: &Panel) -> Option<PanelRect> {
    let (w, h) = (size.0 as i32, size.1 as i32);
    let (rows, cols) = grid;
    if rows == 0 || cols == 0 {
        return None;
    }
    let (x0, y0, x1, y1) = match p.bounds {
        Some((x, y, pw, ph)) => {
            let left = (x * w as f64).round() as i32;
            let top = ((1.0 - y - ph) * h as f64).round() as i32;
            let right = (w as f64 - (x + pw) * w as f64).round() as i32;
            let bottom = (y * h as f64).round() as i32;
            (left, top, w - right, h - bottom)
        }
        None => {
            let row = p.pos / cols;
            let col = p.pos % cols;
            if row >= rows || col >= cols {
                return None;
            }
            (
                split_evenly(0, w, cols, col),
                split_evenly(0, h, rows, row),
                split_evenly(0, w, cols, col + 1),
                split_evenly(0, h, rows, row + 1),
            )
        }
    };
    let (x0, y0) = (x0.clamp(0, w), y0.clamp(0, h));
    let (x1, y1) = (x1.clamp(0, w), y1.clamp(0, h));
    if x1 <= x0 || y1 <= y0 {
        return None;
    }
    Some(PanelRect {
        x: x0,
        y: y0,
        w: (x1 - x0) as u32,
        h: (y1 - y0) as u32,
    })
}

fn oversample_scale(size: (u32, u32)) -> u32 {
    let area = size.0 as u64 * size.1 as u64;
    if area.saturating_mul((OVERSAMPLE * OVERSAMPLE) as u64) <= MAX_CANVAS_AREA {
        OVERSAMPLE
    } else {
        1
    }
}

fn downsample(
    rgb: &[u8],
    width: u32,
    height: u32,
    scale: u32,
) -> Result<tiny_skia::Pixmap, String> {
    let mut pixmap =
        tiny_skia::Pixmap::new(width, height).ok_or("failed to allocate panel pixmap")?;
    let samples = (scale * scale) as u64;
    for y in 0..height {
        for x in 0..width {
            let (mut r, mut g, mut b) = (0u64, 0u64, 0u64);
            for sy in 0..scale {
                for sx in 0..scale {
                    let px = x * scale + sx;
                    let py = y * scale + sy;
                    let offset = (py * width * scale + px) as usize * 3;
                    r += rgb[offset] as u64;
                    g += rgb[offset + 1] as u64;
                    b += rgb[offset + 2] as u64;
                }
            }
            pixmap.pixels_mut()[(y * width + x) as usize] =
                tiny_skia::PremultipliedColorU8::from_rgba(
                    (r / samples) as u8,
                    (g / samples) as u8,
                    (b / samples) as u8,
                    255,
                )
                .ok_or("invalid downsampled pixel")?;
        }
    }
    Ok(pixmap)
}

fn render_panel(
    p: &Panel,
    rect: PanelRect,
    scale: u32,
    background: [u8; 3],
) -> Result<tiny_skia::Pixmap, String> {
    let (pw, ph) = (rect.w, rect.h);
    let (bw, bh) = (pw * scale, ph * scale);
    let mut rgb = vec![0u8; bw as usize * bh as usize * 3];
    for px in rgb.as_chunks_mut::<3>().0 {
        *px = background;
    }
    {
        let backend = BitMapBackend::with_buffer(&mut rgb, (bw, bh));
        let area = ScaleBackend::new(backend, scale).into_drawing_area();
        let mut overlays = Vec::new();
        // `text_px` compensates for the SVG backend's 1.24 font divisor; the
        // bitmap backend applies the font size directly.
        draw_panel(&area, p, &mut overlays, 0, false, p.dpi / 1.24).map_err(|e| e.to_string())?;
        area.present().map_err(|e| e.to_string())?;
    }
    downsample(&rgb, pw, ph, scale)
}

fn panel_work(p: &Panel) -> usize {
    let mut count = 0usize;
    for s in &p.series {
        count = count.saturating_add(s.x.as_array().len().min(s.y.as_array().len()));
    }
    for sc in &p.scatter {
        count = count.saturating_add(sc.x.as_array().len().min(sc.y.as_array().len()));
    }
    for e in &p.errors {
        count = count.saturating_add(e.0.as_array().len());
    }
    for c in &p.contours {
        count = count.saturating_add(c.0.as_array().len().saturating_mul(c.1.as_array().len()));
    }
    for b in &p.bars {
        count = count.saturating_add(b.left.as_array().len());
    }
    for b in &p.bands {
        count = count.saturating_add(b.x.as_array().len());
    }
    for patch in &p.patches {
        count = count.saturating_add(patch.points.len() / 2 + 1);
    }
    for coll in &p.collections {
        count = count.saturating_add(coll.points.len() / 2);
        for segment in &coll.segments {
            count = count.saturating_add(segment.len() / 2);
        }
    }
    count
}

/// Matches the dense marker-layer threshold in `draw_panel`.
const DENSE_MARKER_THRESHOLD: usize = 4_096;

/// The SVG path batches dense marker layers into one bitmap overlay. Direct
/// rendering draws every marker separately at 2x, which is much slower for
/// scatter-heavy panels, so those stay on the SVG path.
fn has_dense_markers(p: &Panel) -> bool {
    let scatter = p
        .scatter
        .iter()
        .map(|sc| sc.x.as_array().len().min(sc.y.as_array().len()))
        .sum::<usize>();
    let series = p
        .series
        .iter()
        .filter(|s| !s.marker.is_empty() && s.markersize > 0.0)
        .map(|s| s.x.as_array().len().min(s.y.as_array().len()))
        .sum::<usize>();
    let collections = p
        .collections
        .iter()
        .map(|coll| coll.points.len() / 2)
        .sum::<usize>();
    scatter >= DENSE_MARKER_THRESHOLD
        || series >= DENSE_MARKER_THRESHOLD
        || collections >= DENSE_MARKER_THRESHOLD
}

/// Direct bitmap rendering has a fixed oversampling cost, so it pays off on
/// multi-panel figures and panels with enough primitives to amortise it. Tiny
/// single-panel plots and marker-heavy panels keep the faster SVG + resvg path.
pub(crate) fn direct_eligible(panels: &[Panel]) -> bool {
    if panels.iter().any(has_dense_markers) {
        return false;
    }
    panels.len() > 1
        || panels.iter().fold(0usize, |total, panel| {
            total.saturating_add(panel_work(panel))
        }) >= 1_000
}

/// Render all panels directly into one opaque RGBA pixmap.
pub(crate) fn render_png(
    size: (u32, u32),
    grid: (usize, usize),
    panels: &[Panel],
    background: [u8; 3],
) -> Result<tiny_skia::Pixmap, String> {
    let scale = oversample_scale(size);
    let rendered: Vec<Result<(PanelRect, tiny_skia::Pixmap), String>> = panels
        .par_iter()
        .map(|p| {
            let rect = panel_rect(size, grid, p).ok_or("subplot index out of range")?;
            let pixmap = render_panel(p, rect, scale, background)?;
            Ok((rect, pixmap))
        })
        .collect();
    let mut out =
        tiny_skia::Pixmap::new(size.0, size.1).ok_or("failed to allocate figure pixmap")?;
    out.fill(tiny_skia::Color::from_rgba8(
        background[0],
        background[1],
        background[2],
        255,
    ));
    for (rect, panel) in rendered.into_iter().collect::<Result<Vec<_>, String>>()? {
        let (dst, src) = (out.data_mut(), panel.data());
        let src_stride = rect.w as usize * 4;
        let dst_stride = size.0 as usize * 4;
        for row in 0..rect.h as usize {
            let s = row * src_stride;
            let d = (rect.y as usize + row) * dst_stride + rect.x as usize * 4;
            dst[d..d + src_stride].copy_from_slice(&src[s..s + src_stride]);
        }
    }
    Ok(out)
}
