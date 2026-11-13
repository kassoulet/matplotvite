use std::collections::{HashMap, VecDeque};
use std::sync::{Arc, Mutex, OnceLock};

use pdf_writer::{Content, Finish, Name, Pdf, Rect, Ref};
use plotters::prelude::*;
use plotters::style::text_anchor::{HPos, Pos, VPos};
use plotters::style::IntoFont;
use rayon::prelude::*;

use crate::color::color;
use crate::draw::{draw_label, draw_panel, text_px};
use crate::fonts::{fontdb, pdf_options};
use crate::model::{Panel, PngCompression, Suptitle, TextItem};

/// Figure-level marks (title, text and border) drawn after every panel.
pub(crate) struct FigureDecorations<'a> {
    pub(crate) suptitle: Option<Suptitle<'a>>,
    pub(crate) texts: &'a [TextItem],
    pub(crate) edgecolor: Option<&'a str>,
}

impl FigureDecorations<'_> {
    pub(crate) fn is_empty(&self) -> bool {
        self.suptitle.is_none() && self.edgecolor.is_none() && self.texts.is_empty()
    }
}

/// Convert SVG markup into a single-page vector PDF. `dpi` sets the physical
/// page size: the SVG's pixel dimensions are treated as `dpi` pixels per inch.
/// Tight output crops the page in the same parse that builds the content.
pub(crate) fn render_pdf(
    svg: &str,
    dpi: f64,
    size: (u32, u32),
    tight: bool,
    background: Option<RGBAColor>,
) -> Result<Vec<u8>, String> {
    let tree = svg2pdf::usvg::Tree::from_str(svg, &pdf_options()).map_err(|e| e.to_string())?;
    let scale = (72.0 / dpi) as f32;
    let (crop_x, crop_y, crop_w, crop_h) = if tight {
        pdf_bounds(&tree, size).unwrap_or((0, 0, size.0, size.1))
    } else {
        (0, 0, size.0, size.1)
    };
    let full_w = size.0 as f32 * scale;
    let full_h = size.1 as f32 * scale;
    let page_w = crop_w as f32 * scale;
    let page_h = crop_h as f32 * scale;

    let mut alloc = Ref::new(1);
    let catalog_id = alloc.bump();
    let page_tree_id = alloc.bump();
    let page_id = alloc.bump();
    let content_id = alloc.bump();
    let svg_name = Name(b"S1");

    let (svg_chunk, svg_id) = svg2pdf::to_chunk(&tree, svg2pdf::ConversionOptions::default())
        .map_err(|e| e.to_string())?;
    let mut map = HashMap::new();
    let svg_chunk = svg_chunk.renumber(|old| *map.entry(old).or_insert_with(|| alloc.bump()));
    let svg_id = *map.get(&svg_id).ok_or("failed to remap embedded SVG")?;

    let mut pdf = Pdf::new();
    pdf.catalog(catalog_id).pages(page_tree_id);
    pdf.pages(page_tree_id).kids([page_id]).count(1);

    let mut page = pdf.page(page_id);
    page.media_box(Rect::new(0.0, 0.0, page_w, page_h));
    page.parent(page_tree_id);
    page.contents(content_id);
    let mut resources = page.resources();
    resources.x_objects().pair(svg_name, svg_id);
    resources.finish();
    page.finish();

    // The SVG is embedded as a 1x1 XObject, so scale it to the full figure and
    // then shift the requested crop to the page origin. PDF y grows upwards.
    let mut content = Content::new();
    if let Some([r, g, b, _]) = background.and_then(|bg| background_pixel(Some(bg))) {
        // PDF has no figure transparency; match the PNG path by pre-blending
        // the background colour over white.
        content.set_fill_rgb(r as f32 / 255.0, g as f32 / 255.0, b as f32 / 255.0);
        content.rect(0.0, 0.0, page_w, page_h);
        content.fill_nonzero();
    }
    content
        .transform([
            full_w,
            0.0,
            0.0,
            full_h,
            -(crop_x as f32) * scale,
            -((size.1 - crop_y - crop_h) as f32) * scale,
        ])
        .x_object(svg_name);
    pdf.stream(content_id, &content.finish());
    pdf.extend(&svg_chunk);
    Ok(pdf.finish())
}

/// Geometric bounds for the PDF copy of `usvg`, rounded outwards to whole
/// canvas pixels so the page is not clipped by fractional geometry.
fn pdf_bounds(tree: &svg2pdf::usvg::Tree, (w, h): (u32, u32)) -> Option<Bbox> {
    let (x0, y0, x1, y1) = pdf_group_bounds(tree.root())?;
    if !x0.is_finite() || !y0.is_finite() || !x1.is_finite() || !y1.is_finite() {
        return None;
    }
    let x0 = x0.floor().clamp(0.0, w as f32);
    let y0 = y0.floor().clamp(0.0, h as f32);
    let x1 = x1.ceil().clamp(0.0, w as f32);
    let y1 = y1.ceil().clamp(0.0, h as f32);
    if x1 <= x0 || y1 <= y0 {
        return None;
    }
    Some((x0 as u32, y0 as u32, (x1 - x0) as u32, (y1 - y0) as u32))
}

/// usvg 0.45 applies an image's viewBox transform to its bounding box twice,
/// so an image group reports a huge rectangle. Rebuild image bounds from the
/// intrinsic image size and its absolute transform instead.
fn pdf_node_bounds(node: &svg2pdf::usvg::Node) -> Option<(f32, f32, f32, f32)> /* left, top, right, bottom */
{
    match node {
        svg2pdf::usvg::Node::Group(group) => pdf_group_bounds(group),
        svg2pdf::usvg::Node::Image(image) => {
            let size = image.size();
            let rect = svg2pdf::usvg::Rect::from_xywh(0.0, 0.0, size.width(), size.height())?;
            let rect = rect.transform(image.abs_transform())?;
            Some((rect.left(), rect.top(), rect.right(), rect.bottom()))
        }
        _ => {
            let rect = node.abs_stroke_bounding_box();
            Some((rect.left(), rect.top(), rect.right(), rect.bottom()))
        }
    }
}

fn pdf_group_bounds(group: &svg2pdf::usvg::Group) -> Option<(f32, f32, f32, f32)> {
    let mut bounds: Option<(f32, f32, f32, f32)> = None;
    for child in group.children() {
        let Some((l, t, r, b)) = pdf_node_bounds(child) else {
            continue;
        };
        bounds = Some(match bounds {
            Some((bl, bt, br, bb)) => (bl.min(l), bt.min(t), br.max(r), bb.max(b)),
            None => (l, t, r, b),
        });
    }
    bounds
}

/// The fill used by the rasterised and vector figure background. `None` keeps
/// the figure transparent.
pub(crate) fn figure_background(transparent: bool, facecolor: Option<&str>) -> Option<RGBAColor> {
    if transparent {
        None
    } else {
        Some(
            facecolor
                .map(color)
                .unwrap_or(RGBAColor(255, 255, 255, 1.0)),
        )
    }
}

/// The body of an SVG document, without its root tag.
fn svg_body(svg: &str) -> &str {
    let Some(start) = svg.find('>') else {
        return "";
    };
    let Some(end) = svg.rfind("</svg>") else {
        return "";
    };
    &svg[start + 1..end]
}

type PanelFragment = (String, Vec<String>);

/// A full SVG fragment can be megabytes for a dense scatter, so entry count
/// alone is not a useful bound. Evict oldest insertions once either the entry
/// or byte budget is reached; one oversized fragment is simply not cached.
struct PanelCache {
    entries: HashMap<String, Arc<PanelFragment>>,
    order: VecDeque<String>,
    bytes: usize,
}

impl PanelCache {
    const MAX_BYTES: usize = 64 * 1024 * 1024;
    const MAX_ENTRIES: usize = 256;

    fn new() -> Self {
        Self {
            entries: HashMap::new(),
            order: VecDeque::new(),
            bytes: 0,
        }
    }

    fn get(&self, key: &str) -> Option<Arc<PanelFragment>> {
        self.entries.get(key).cloned()
    }

    fn insert(&mut self, key: String, fragment: Arc<PanelFragment>) {
        let bytes = fragment_bytes(&fragment);
        if bytes > Self::MAX_BYTES {
            return;
        }
        while !self.order.is_empty()
            && (self.bytes + bytes > Self::MAX_BYTES || self.entries.len() >= Self::MAX_ENTRIES)
        {
            let Some(old_key) = self.order.pop_front() else {
                break;
            };
            if let Some(old) = self.entries.remove(&old_key) {
                self.bytes = self.bytes.saturating_sub(fragment_bytes(&old));
            }
        }
        if let Some(old) = self.entries.insert(key.clone(), fragment) {
            self.bytes = self.bytes.saturating_sub(fragment_bytes(&old));
        } else {
            self.order.push_back(key);
        }
        self.bytes += bytes;
    }
}

fn fragment_bytes(fragment: &PanelFragment) -> usize {
    fragment.0.len() + fragment.1.iter().map(String::len).sum::<usize>()
}

static PANEL_CACHE: OnceLock<Mutex<PanelCache>> = OnceLock::new();

/// Draw one panel into a full-size transparent SVG and return its body. Each
/// fragment uses absolute canvas coordinates, so the bodies can simply be
/// concatenated in panel order.
fn panel_fragment(
    size: (u32, u32),
    grid: (usize, usize),
    p: &Panel,
    top_pad: i32,
    raster_scatter: bool,
) -> Result<(String, Vec<String>), String> {
    let (w, h) = size;
    let mut svg = String::new();
    let mut overlays = Vec::new();
    {
        let root = SVGBackend::with_string(&mut svg, size).into_drawing_area();
        let content = root.margin(top_pad, 0, 0, 0);
        let cells = content.split_evenly(grid);
        let gap = if p.twin_reserve.is_empty() {
            0
        } else {
            (p.twin_gap * w as f64).round() as i32
        };
        match p.bounds {
            Some((x, y, pw, ph)) => {
                let left = (x * w as f64).round() as i32;
                let top = ((1.0 - y - ph) * h as f64).round() as i32;
                let right = (w as f64 - (x + pw) * w as f64).round() as i32;
                let bottom = (y * h as f64).round() as i32;
                let area = root.margin(top.max(0), bottom.max(0), left.max(0), right.max(0));
                draw_panel(
                    &area,
                    p,
                    &mut overlays,
                    gap,
                    raster_scatter,
                    false,
                    p.dpi,
                    1.0 / 1.24,
                )
                .map_err(|e| e.to_string())?;
            }
            None => draw_panel(
                cells.get(p.pos).ok_or("subplot index out of range")?,
                p,
                &mut overlays,
                gap,
                raster_scatter,
                false,
                p.dpi,
                1.0 / 1.24,
            )
            .map_err(|e| e.to_string())?,
        }
        root.present().map_err(|e| e.to_string())?;
    }
    Ok((svg_body(&svg).to_string(), overlays))
}

fn fragment_key(
    size: (u32, u32),
    grid: (usize, usize),
    p: &Panel,
    top_pad: i32,
    raster_scatter: bool,
) -> String {
    // `cache_key` is a 128-bit blake2b digest; keep all of it instead of
    // folding it into a 64-bit hash. Raster and vector output differ for dense
    // scatter, so the mode is part of the key too.
    format!(
        "{}:{}x{}:{}x{}:{}:{}",
        p.cache_key,
        size.0,
        size.1,
        grid.0,
        grid.1,
        top_pad,
        if raster_scatter { 1 } else { 0 }
    )
}

/// Reuse the encoded/drawn fragment of an unchanged panel; only dirty panels
/// are handed back to the drawing code (and to Rayon).
fn cached_panel_fragment(
    size: (u32, u32),
    grid: (usize, usize),
    p: &Panel,
    top_pad: i32,
    raster_scatter: bool,
) -> Result<Arc<PanelFragment>, String> {
    if p.cache_key.is_empty() {
        return panel_fragment(size, grid, p, top_pad, raster_scatter).map(Arc::new);
    }
    let key = fragment_key(size, grid, p, top_pad, raster_scatter);
    let cache = PANEL_CACHE.get_or_init(|| Mutex::new(PanelCache::new()));
    if let Ok(guard) = cache.lock() {
        if let Some(fragment) = guard.get(&key) {
            return Ok(fragment);
        }
    }
    let fragment = Arc::new(panel_fragment(size, grid, p, top_pad, raster_scatter)?);
    if let Ok(mut guard) = cache.lock() {
        guard.insert(key, Arc::clone(&fragment));
    }
    Ok(fragment)
}

/// Figure-level decorations (title, text and border), drawn after all panels.
fn decoration_fragment(
    size: (u32, u32),
    decorations: &FigureDecorations<'_>,
    dpi: f64,
) -> Result<String, String> {
    let (w, h) = size;
    let mut svg = String::new();
    {
        let root = SVGBackend::with_string(&mut svg, size).into_drawing_area();
        if let Some(ref s) = decorations.suptitle {
            let style = (s.family, text_px(s.size.max(6.0), dpi).round() as u32)
                .into_font()
                .color(&BLACK);
            root.draw(&Text::new(
                s.text.to_string(),
                ((s.x * w as f64) as i32, ((1.0 - s.y) * h as f64) as i32),
                style.pos(Pos::new(HPos::Center, VPos::Center)),
            ))
            .map_err(|e| e.to_string())?;
        }
        for (x, y, text, colour, size, ha, va, bbox, rotation, family) in decorations.texts {
            // Figure coordinates are fractions of the canvas, like `fig.text`.
            draw_label(
                &root,
                (0, 0),
                ((x * w as f64) as i32, ((1.0 - y) * h as f64) as i32),
                text,
                color(colour),
                text_px(*size, dpi).max(1.0),
                ha,
                va,
                bbox.as_ref(),
                *rotation,
                1.0 / 1.24,
                family,
            )
            .map_err(|e| e.to_string())?;
        }
        if let Some(ec) = decorations.edgecolor {
            root.draw(&Rectangle::new(
                [(0, 0), (w as i32 - 1, h as i32 - 1)],
                color(ec).stroke_width(1),
            ))
            .map_err(|e| e.to_string())?;
        }
        root.present().map_err(|e| e.to_string())?;
    }
    Ok(svg_body(&svg).to_string())
}

/// A root SVG containing only the figure background; panels are inserted later.
fn background_fragment(size: (u32, u32), background: Option<RGBAColor>) -> Result<String, String> {
    let mut svg = String::new();
    {
        let root = SVGBackend::with_string(&mut svg, size).into_drawing_area();
        if let Some(bg) = background {
            root.fill(&bg).map_err(|e| e.to_string())?;
        }
        root.present().map_err(|e| e.to_string())?;
    }
    Ok(svg)
}

/// Encoding mode for the figure: DPI scales point-based text, and raster
/// formats may use raster marker layers.
pub(crate) struct RenderOutput {
    pub(crate) dpi: f64,
    pub(crate) raster: bool,
    /// Compute tight bounds from SVG geometry (vector output) instead of
    /// rasterising the whole figure just to measure it.
    pub(crate) tight_bounds: bool,
}

/// Render all panels to an SVG string via plotters. Independent panels are
/// rasterised/drawn concurrently with Rayon and concatenated in panel order.
pub(crate) fn render_svg(
    size: (u32, u32),
    grid: (usize, usize),
    panels: &[Panel],
    background: Option<RGBAColor>,
    decorations: FigureDecorations<'_>,
    output: RenderOutput,
) -> Result<(String, Option<Bbox>), String> {
    let dpi = output.dpi;
    // A figure title reserves a band at the top so it never overlaps the first
    // row of panels.
    let top_pad = decorations
        .suptitle
        .as_ref()
        .map(|s| (text_px(s.size, dpi.max(1.0)) * 1.6).round() as i32 + 8)
        .unwrap_or(0);
    let fragments: Vec<Arc<PanelFragment>> = panels
        .par_iter()
        .map(|p| cached_panel_fragment(size, grid, p, top_pad, output.raster))
        .collect::<Result<_, String>>()?;
    let decoration_svg = if decorations.is_empty() {
        None
    } else {
        Some(decoration_fragment(size, &decorations, dpi)?)
    };

    // Build the document in one pass. Inserting each fragment before
    // `</svg>` shifted the whole tail once per panel and overlay. The figure
    // background is added after measuring so it cannot hide the content bounds.
    let body = background_fragment(size, None)?;
    // Tight bounds must be measured without the full-page background; all
    // other output can write the background in place instead of shifting the
    // completed document once.
    let background_body = if background.is_some() && !output.tight_bounds {
        Some(background_fragment(size, background)?)
    } else {
        None
    };
    let insert_at = body
        .rfind("</svg>")
        .ok_or("rendered SVG has no closing tag")?;
    let overlay_count = fragments.iter().map(|f| f.1.len()).sum::<usize>();
    let extra = fragments.iter().map(|f| fragment_bytes(f)).sum::<usize>()
        + decoration_svg.as_ref().map_or(0, String::len)
        + fragments.len()
        + overlay_count
        + if decoration_svg.is_some() { 1 } else { 0 };
    let mut svg = String::with_capacity(body.len() + extra);
    svg.push_str(&body[..insert_at]);
    if let Some(background_body) = &background_body {
        svg.push_str(svg_body(background_body));
    }
    for fragment in &fragments {
        svg.push_str(&fragment.0);
        svg.push('\n');
    }
    for fragment in &fragments {
        for overlay in &fragment.1 {
            svg.push_str(overlay);
            svg.push('\n');
        }
    }
    if let Some(decoration) = &decoration_svg {
        svg.push_str(decoration);
        svg.push('\n');
    }
    svg.push_str(&body[insert_at..]);
    let bounds = if output.tight_bounds {
        svg_bounds(&svg, size)
    } else {
        None
    };
    if output.tight_bounds && background.is_some() {
        let background = background_fragment(size, background)?;
        let background = svg_body(&background);
        let root_end = svg.find('>').ok_or("rendered SVG has no root tag")? + 1;
        svg.insert_str(root_end, background);
    }
    Ok((svg, bounds))
}

/// Geometric bounds of the drawn content, including strokes and text, in
/// canvas pixels. The figure background is deliberately absent from `svg`.
fn svg_bounds(svg: &str, (w, h): (u32, u32)) -> Option<Bbox> {
    let opts = usvg::Options {
        fontdb: fontdb(),
        ..Default::default()
    };
    let tree = usvg::Tree::from_str(svg, &opts).ok()?;
    let rect = tree.root().abs_stroke_bounding_box();
    if !rect.width().is_finite() || !rect.height().is_finite() {
        return None;
    }
    let x0 = rect.left().floor().clamp(0.0, w as f32);
    let y0 = rect.top().floor().clamp(0.0, h as f32);
    let x1 = rect.right().ceil().clamp(0.0, w as f32);
    let y1 = rect.bottom().ceil().clamp(0.0, h as f32);
    if x1 <= x0 || y1 <= y0 {
        return None;
    }
    Some((x0 as u32, y0 as u32, (x1 - x0) as u32, (y1 - y0) as u32))
}

/// Rasterise an SVG string via resvg + tiny-skia.
/// Fonts embedded in `build_fontdb()` are used — no system fonts needed.
pub(crate) fn rasterize(
    svg: &str,
    w: u32,
    h: u32,
    transparent: bool,
) -> Result<tiny_skia::Pixmap, String> {
    let opts = usvg::Options {
        fontdb: fontdb(),
        ..Default::default()
    };
    let tree = usvg::Tree::from_str(svg, &opts).map_err(|e| e.to_string())?;
    let mut pixmap = tiny_skia::Pixmap::new(w, h).ok_or("failed to allocate pixmap")?;
    if !transparent {
        pixmap.fill(tiny_skia::Color::WHITE);
    }
    resvg::render(
        &tree,
        tiny_skia::Transform::identity(),
        &mut pixmap.as_mut(),
    );
    Ok(pixmap)
}

/// Encode a pixmap as PNG. This matches `tiny_skia::Pixmap::encode_png`
/// (including alpha demultiplication) but exposes the compression level because
/// the default level dominates save time for typical figure sizes.
///
/// `opaque` means every pixel has alpha 255, which holds whenever the figure is
/// composited over a solid background. Premultiplied and straight-alpha pixels
/// are then identical, so the buffer is encoded directly instead of being
/// copied and demultiplied first. That removes a full-frame pass (and a
/// full-frame allocation) from the common save path.
pub(crate) fn encode_png(
    pixmap: &tiny_skia::Pixmap,
    compression: PngCompression,
    opaque: bool,
) -> Result<Vec<u8>, png::EncodingError> {
    let (width, height) = (pixmap.width(), pixmap.height());
    if opaque {
        encode_png_data(pixmap.data(), width, height, compression)
    } else {
        let rgba = demultiply(pixmap);
        encode_png_data(&rgba, width, height, compression)
    }
}

/// Convert a premultiplied pixmap to straight-alpha RGBA in one allocation.
/// `Pixmap::to_owned().take_demultiplied()` did the same conversion but first
/// cloned the entire pixmap.
fn demultiply(pixmap: &tiny_skia::Pixmap) -> Vec<u8> {
    let mut rgba = pixmap.data().to_vec();
    for px in rgba.as_chunks_mut::<4>().0 {
        let a = px[3] as u32;
        match a {
            0 => px[..3].fill(0),
            255 => {}
            _ => {
                for c in &mut px[..3] {
                    *c = ((*c as u32 * 255 + a / 2) / a).min(255) as u8;
                }
            }
        }
    }
    rgba
}

fn encode_png_data(
    rgba: &[u8],
    width: u32,
    height: u32,
    compression: PngCompression,
) -> Result<Vec<u8>, png::EncodingError> {
    let mut out = Vec::new();
    {
        let mut encoder = png::Encoder::new(&mut out, width, height);
        encoder.set_color(png::ColorType::Rgba);
        encoder.set_depth(png::BitDepth::Eight);
        encoder.set_compression(compression.to_png());
        encoder.set_filter(png::Filter::Sub);
        let mut writer = encoder.write_header()?;
        writer.write_image_data(rgba)?;
    }
    Ok(out)
}

/// Encode a pixmap as lossless WebP, matching the PNG alpha handling.
pub(crate) fn encode_webp(pixmap: &tiny_skia::Pixmap) -> Result<Vec<u8>, String> {
    let rgba = demultiply(pixmap);
    let encoded =
        webp::Encoder::from_rgba(&rgba, pixmap.width(), pixmap.height()).encode_lossless();
    Ok(encoded.to_vec())
}

pub(crate) type Bbox = (u32, u32, u32, u32); // x, y, width, height

/// The opaque pixel produced by painting `background` over the rasteriser's
/// white canvas. `None` means the figure is transparent.
pub(crate) fn background_pixel(background: Option<RGBAColor>) -> Option<[u8; 4]> {
    background.map(|c| {
        let a = c.3.clamp(0.0, 1.0);
        let channel = |v: u8| (v as f64 * a + 255.0 * (1.0 - a)).round() as u8;
        [channel(c.0), channel(c.1), channel(c.2), 255]
    })
}

/// Smallest rectangle containing drawn pixels, or `None` if the figure is blank.
pub(crate) fn content_bbox(
    pixmap: &tiny_skia::Pixmap,
    background: Option<[u8; 4]>,
) -> Option<Bbox> {
    let (w, h) = (pixmap.width(), pixmap.height());
    let data = pixmap.data();
    let (mut x0, mut y0, mut x1, mut y1) = (w, h, 0u32, 0u32);
    let mut found = false;
    for (y, row) in data.chunks_exact(w as usize * 4).enumerate() {
        let mut row_found = false;
        for (x, px) in row.as_chunks::<4>().0.iter().enumerate() {
            let drawn = match background {
                None => px[3] != 0,
                Some(bg) => px.as_slice() != bg.as_slice(),
            };
            if drawn {
                row_found = true;
                x0 = x0.min(x as u32);
                x1 = x1.max(x as u32);
            }
        }
        if row_found {
            found = true;
            y0 = y0.min(y as u32);
            y1 = y as u32;
        }
    }
    found.then(|| (x0, y0, x1 - x0 + 1, y1 - y0 + 1))
}

/// Copy `bbox` out of a pixmap — used for `bbox_inches="tight"` PNGs.
pub(crate) fn crop_pixmap(
    pixmap: &tiny_skia::Pixmap,
    (bx, by, bw, bh): Bbox,
) -> Result<tiny_skia::Pixmap, String> {
    let mut out = tiny_skia::Pixmap::new(bw, bh).ok_or("failed to allocate pixmap")?;
    let (src, sw) = (pixmap.data(), pixmap.width());
    let src_stride = sw as usize * 4;
    let dst_stride = bw as usize * 4;
    let x_offset = bx as usize * 4;
    let dst = out.data_mut();
    for y in 0..bh as usize {
        let s = (by as usize + y) * src_stride + x_offset;
        let d = y * dst_stride;
        dst[d..d + dst_stride].copy_from_slice(&src[s..s + dst_stride]);
    }
    Ok(out)
}

/// Remove `name="..."` from an SVG tag string.
pub(crate) fn drop_attr(tag: &str, name: &str) -> String {
    let pat = format!("{name}=\"");
    let Some(i) = tag.find(&pat) else {
        return tag.to_string();
    };
    let start = if i > 0 && tag.as_bytes()[i - 1] == b' ' {
        i - 1
    } else {
        i
    };
    let vstart = i + pat.len();
    let vend = tag[vstart..]
        .find('"')
        .map(|j| vstart + j + 1)
        .unwrap_or(tag.len());
    format!("{}{}", &tag[..start], &tag[vend..])
}

/// Crop an SVG by rewriting its root width/height/viewBox — stays vector.
pub(crate) fn svg_tight(svg: &str, (bx, by, bw, bh): Bbox) -> Option<String> {
    let start = svg.find("<svg")?;
    let end = start + svg[start..].find('>')?;
    let mut tag = svg[start..end].to_string();
    for attr in ["width", "height", "viewBox"] {
        tag = drop_attr(&tag, attr);
    }
    let tag = format!("{tag} width=\"{bw}\" height=\"{bh}\" viewBox=\"{bx} {by} {bw} {bh}\"");
    Some(format!("{}{}{}", &svg[..start], tag, &svg[end..]))
}
