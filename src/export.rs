use std::collections::hash_map::DefaultHasher;
use std::collections::HashMap;
use std::hash::{Hash, Hasher};
use std::sync::{Mutex, OnceLock};

use plotters::prelude::*;
use plotters::style::text_anchor::{HPos, Pos, VPos};
use plotters::style::IntoFont;
use rayon::prelude::*;

use crate::color::color;
use crate::draw::{draw_panel, text_px};
use crate::fonts::{fontdb, pdf_options};
use crate::model::{Panel, PngCompression, Suptitle};

/// Convert SVG markup into a single-page vector PDF. `dpi` sets the physical
/// page size: the SVG's pixel dimensions are treated as `dpi` pixels per inch.
pub(crate) fn render_pdf(svg: &str, dpi: f64) -> Result<Vec<u8>, String> {
    let opts = pdf_options();
    let tree = svg2pdf::usvg::Tree::from_str(svg, &opts).map_err(|e| e.to_string())?;
    let page = svg2pdf::PageOptions { dpi: dpi as f32 };
    svg2pdf::to_pdf(&tree, svg2pdf::ConversionOptions::default(), page).map_err(|e| e.to_string())
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

/// Insert a fragment immediately before the closing `</svg>` tag.
fn append_body(svg: &mut String, body: &str) {
    if let Some(at) = svg.rfind("</svg>") {
        svg.insert_str(at, body);
        svg.insert(at + body.len(), '\n');
    }
}

type PanelFragment = (String, Vec<String>);
type PanelCache = Mutex<HashMap<u64, PanelFragment>>;

static PANEL_CACHE: OnceLock<PanelCache> = OnceLock::new();

/// Draw one panel into a full-size transparent SVG and return its body. Each
/// fragment uses absolute canvas coordinates, so the bodies can simply be
/// concatenated in panel order.
fn panel_fragment(
    size: (u32, u32),
    grid: (usize, usize),
    p: &Panel,
    top_pad: i32,
) -> Result<(String, Vec<String>), String> {
    let (w, h) = size;
    let mut svg = String::new();
    let mut overlays = Vec::new();
    {
        let root = SVGBackend::with_string(&mut svg, size).into_drawing_area();
        let content = root.margin(top_pad, 0, 0, 0);
        let cells = content.split_evenly(grid);
        let gap = if p.twin.is_empty() {
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
                draw_panel(&area, p, &mut overlays, gap).map_err(|e| e.to_string())?;
            }
            None => draw_panel(
                cells.get(p.pos).ok_or("subplot index out of range")?,
                p,
                &mut overlays,
                gap,
            )
            .map_err(|e| e.to_string())?,
        }
        root.present().map_err(|e| e.to_string())?;
    }
    Ok((svg_body(&svg).to_string(), overlays))
}

fn fragment_key(size: (u32, u32), grid: (usize, usize), p: &Panel, top_pad: i32) -> u64 {
    let mut hasher = DefaultHasher::new();
    p.cache_key.hash(&mut hasher);
    size.hash(&mut hasher);
    grid.hash(&mut hasher);
    top_pad.hash(&mut hasher);
    hasher.finish()
}

/// Reuse the encoded/drawn fragment of an unchanged panel; only dirty panels
/// are handed back to the drawing code (and to Rayon).
fn cached_panel_fragment(
    size: (u32, u32),
    grid: (usize, usize),
    p: &Panel,
    top_pad: i32,
) -> Result<PanelFragment, String> {
    if p.cache_key.is_empty() {
        return panel_fragment(size, grid, p, top_pad);
    }
    let key = fragment_key(size, grid, p, top_pad);
    let cache = PANEL_CACHE.get_or_init(|| Mutex::new(HashMap::new()));
    if let Ok(guard) = cache.lock() {
        if let Some(fragment) = guard.get(&key) {
            return Ok(fragment.clone());
        }
    }
    let fragment = panel_fragment(size, grid, p, top_pad)?;
    if let Ok(mut guard) = cache.lock() {
        if guard.len() >= 256 {
            guard.clear();
        }
        guard.insert(key, fragment.clone());
    }
    Ok(fragment)
}

/// Figure-level decorations (title and border), drawn after all panels.
fn decoration_fragment(
    size: (u32, u32),
    suptitle: Option<Suptitle>,
    edgecolor: Option<&str>,
    dpi: f64,
) -> Result<String, String> {
    let (w, h) = size;
    let mut svg = String::new();
    {
        let root = SVGBackend::with_string(&mut svg, size).into_drawing_area();
        if let Some(s) = suptitle {
            let style = ("sans-serif", text_px(s.size.max(6.0), dpi).round() as u32)
                .into_font()
                .color(&BLACK);
            root.draw(&Text::new(
                s.text.to_string(),
                ((s.x * w as f64) as i32, ((1.0 - s.y) * h as f64) as i32),
                style.pos(Pos::new(HPos::Center, VPos::Center)),
            ))
            .map_err(|e| e.to_string())?;
        }
        if let Some(ec) = edgecolor {
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

/// Render all panels to an SVG string via plotters. Independent panels are
/// rasterised/drawn concurrently with Rayon and concatenated in panel order.
pub(crate) fn render_svg(
    size: (u32, u32),
    grid: (usize, usize),
    panels: &[Panel],
    background: Option<RGBAColor>,
    edgecolor: Option<&str>,
    suptitle: Option<Suptitle>,
    dpi: f64,
) -> Result<String, String> {
    // A figure title reserves a band at the top so it never overlaps the first
    // row of panels.
    let top_pad = suptitle
        .as_ref()
        .map(|s| (text_px(s.size, dpi.max(1.0)) * 1.6).round() as i32 + 8)
        .unwrap_or(0);
    let fragments: Vec<(String, Vec<String>)> = panels
        .par_iter()
        .map(|p| cached_panel_fragment(size, grid, p, top_pad))
        .collect::<Result<_, String>>()?;
    let (bodies, overlays): (Vec<String>, Vec<Vec<String>>) = fragments.into_iter().unzip();
    let overlays: Vec<String> = overlays.into_iter().flatten().collect();

    let mut svg = background_fragment(size, background)?;
    for body in bodies {
        append_body(&mut svg, &body);
    }
    for overlay in overlays {
        append_body(&mut svg, &overlay);
    }
    if suptitle.is_some() || edgecolor.is_some() {
        let decorations = decoration_fragment(size, suptitle, edgecolor, dpi)?;
        append_body(&mut svg, &decorations);
    }
    Ok(svg)
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
        let rgba = pixmap.to_owned().take_demultiplied();
        encode_png_data(&rgba, width, height, compression)
    }
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
    let copy = pixmap.to_owned();
    let rgba = copy.take_demultiplied();
    let encoded =
        webp::Encoder::from_rgba(&rgba, pixmap.width(), pixmap.height()).encode_lossless();
    Ok(encoded.to_vec())
}

type Bbox = (u32, u32, u32, u32); // x, y, width, height

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
    for y in 0..h {
        for x in 0..w {
            let i = ((y * w + x) * 4) as usize;
            let px = &data[i..i + 4];
            let drawn = match background {
                None => px[3] != 0,
                Some(bg) => px[..4] != bg,
            };
            if drawn {
                found = true;
                x0 = x0.min(x);
                y0 = y0.min(y);
                x1 = x1.max(x);
                y1 = y1.max(y);
            }
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
    for y in 0..bh {
        for x in 0..bw {
            let s = (((by + y) * sw + (bx + x)) * 4) as usize;
            let d = ((y * bw + x) * 4) as usize;
            out.data_mut()[d..d + 4].copy_from_slice(&src[s..s + 4]);
        }
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
