use std::sync::{Arc, OnceLock};

use ab_glyph::{Font, FontRef, PxScale, ScaleFont};
use plotters::style::FontStyle;

// DejaVu Sans (Bitstream Vera licence, see assets/fonts/LICENSE_DEJAVU.txt)
// is Matplotlib's default sans-serif face. Geist remains the serif/mono face.
static FONT_SANS: &[u8] = include_bytes!("../assets/fonts/DejaVuSans.ttf");
static FONT_SANS_BOLD: &[u8] = include_bytes!("../assets/fonts/DejaVuSans-Bold.ttf");
// Geist (OFL, see assets/fonts/LICENSE_GEIST_OFL.txt)
static FONT_SERIF: &[u8] = include_bytes!("../assets/fonts/GeistSerif-Regular.ttf");
static FONT_MONO: &[u8] = include_bytes!("../assets/fonts/GeistMono-Regular.ttf");

/// Advance width of `text` at `px`, using the embedded DejaVu Sans metrics.
/// Falls back to the old character-count estimate if the font cannot load.
pub(crate) fn text_width(text: &str, px: f64) -> f64 {
    let px = px.max(1.0) as f32;
    static SANS_FONT: OnceLock<Option<FontRef<'static>>> = OnceLock::new();
    let Some(font) = SANS_FONT
        .get_or_init(|| FontRef::try_from_slice(FONT_SANS).ok())
        .as_ref()
    else {
        return text.chars().count() as f64 * px as f64 * 0.55;
    };
    let scaled = font.as_scaled(PxScale::from(px));
    text.chars()
        .map(|ch| scaled.h_advance(font.glyph_id(ch)) as f64)
        .sum()
}

/// Register fonts into plotters (for SVG text element names) — called once.
pub(crate) fn register_plotters_fonts() {
    static ONCE: std::sync::Once = std::sync::Once::new();
    ONCE.call_once(|| {
        let _ = plotters::style::register_font("sans-serif", FontStyle::Normal, FONT_SANS);
        let _ = plotters::style::register_font("sans-serif", FontStyle::Bold, FONT_SANS_BOLD);
        let fonts: &[(&str, &[u8])] = &[("serif", FONT_SERIF), ("monospace", FONT_MONO)];
        for (name, bytes) in fonts {
            let _ = plotters::style::register_font(name, FontStyle::Normal, bytes);
        }
    });
}

/// Fonts for the `usvg` bundled with `svg2pdf` (a different major version than
/// the one used for rasterisation), loaded with the same embedded faces.
pub(crate) fn pdf_fontdb() -> Arc<svg2pdf::usvg::fontdb::Database> {
    static FONTDB: OnceLock<Arc<svg2pdf::usvg::fontdb::Database>> = OnceLock::new();
    FONTDB
        .get_or_init(|| {
            let mut db = svg2pdf::usvg::fontdb::Database::new();
            db.load_font_data(FONT_SANS.to_vec());
            db.load_font_data(FONT_SANS_BOLD.to_vec());
            db.load_font_data(FONT_SERIF.to_vec());
            db.load_font_data(FONT_MONO.to_vec());
            db.set_sans_serif_family("DejaVu Sans");
            db.set_serif_family("Geist Serif");
            db.set_monospace_family("Geist Mono");
            Arc::new(db)
        })
        .clone()
}

/// Options for the `usvg` bundled with `svg2pdf`.
pub(crate) fn pdf_options() -> svg2pdf::usvg::Options<'static> {
    svg2pdf::usvg::Options {
        fontdb: pdf_fontdb(),
        ..Default::default()
    }
}

/// Build a fontdb loaded with our embedded faces (for resvg rasterisation).
pub(crate) fn build_fontdb() -> usvg::fontdb::Database {
    let mut db = usvg::fontdb::Database::new();
    db.load_font_data(FONT_SANS.to_vec());
    db.load_font_data(FONT_SANS_BOLD.to_vec());
    db.load_font_data(FONT_SERIF.to_vec());
    db.load_font_data(FONT_MONO.to_vec());
    // Map CSS generic families to the embedded faces
    db.set_sans_serif_family("DejaVu Sans");
    db.set_serif_family("Geist Serif");
    db.set_monospace_family("Geist Mono");
    db
}

/// The embedded font database is immutable, so build it once per process.
pub(crate) fn fontdb() -> Arc<usvg::fontdb::Database> {
    static FONTDB: OnceLock<Arc<usvg::fontdb::Database>> = OnceLock::new();
    FONTDB.get_or_init(|| Arc::new(build_fontdb())).clone()
}
