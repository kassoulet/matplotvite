#![cfg_attr(not(feature = "python"), allow(dead_code))]

mod cmap_data;
mod color;
mod draw;
mod export;
mod fonts;
mod image;
mod layout;
mod model;
mod raster;
mod render;
mod scale;

#[doc(hidden)]
pub mod bench;

#[cfg(feature = "python")]
mod py;

#[cfg(test)]
mod tests {
    use plotters::prelude::RGBAColor;

    use crate::export::{background_pixel, content_bbox, encode_eps, encode_png};
    use crate::layout::range;
    use crate::model::{DrawStyle, LineStyle, Marker, Panel, PngCompression};

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
        fn assert_send_sync<T: Send + Sync>() {}
        assert_send_sync::<Panel>();
    }

    #[test]
    fn drawstyle_parses_supported_names() {
        assert_eq!(DrawStyle::parse("default"), Some(DrawStyle::Normal));
        assert_eq!(DrawStyle::parse("steps-pre"), Some(DrawStyle::StepsPre));
        assert_eq!(DrawStyle::parse("steps-mid"), Some(DrawStyle::StepsMid));
        assert_eq!(DrawStyle::parse("steps-post"), Some(DrawStyle::StepsPost));
        assert_eq!(DrawStyle::parse("steps-middle"), None);
    }

    #[test]
    fn linestyle_parses_names_and_aliases() {
        assert_eq!(LineStyle::parse("-"), Some(LineStyle::Solid));
        assert_eq!(LineStyle::parse("dashed"), Some(LineStyle::Dashed));
        assert_eq!(LineStyle::parse("."), None);
        assert_eq!(LineStyle::parse(":"), Some(LineStyle::Dotted));
        assert_eq!(LineStyle::parse("-."), Some(LineStyle::DashDot));
        assert_eq!(LineStyle::parse("None"), Some(LineStyle::Hidden));
        assert_eq!(LineStyle::parse("bogus"), None);
    }

    #[test]
    fn marker_parses_supported_symbols() {
        assert_eq!(Marker::parse("o"), Some(Marker::Circle));
        assert_eq!(Marker::parse("s"), Some(Marker::Square));
        assert_eq!(Marker::parse("+"), Some(Marker::Plus));
        assert_eq!(Marker::parse(""), Some(Marker::None));
        assert_eq!(Marker::parse("bogus"), None);
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
    fn eps_wraps_the_raster_in_postscript() {
        let mut pixmap = tiny_skia::Pixmap::new(2, 1).unwrap();
        pixmap.pixels_mut()[0] =
            tiny_skia::PremultipliedColorU8::from_rgba(255, 255, 255, 255).unwrap();
        pixmap.pixels_mut()[1] = tiny_skia::PremultipliedColorU8::from_rgba(0, 0, 0, 255).unwrap();
        let eps = String::from_utf8(encode_eps(&pixmap, 72.0)).unwrap();
        assert!(eps.starts_with("%!PS-Adobe-3.0 EPSF-3.0\n"));
        assert!(eps.contains("%%BoundingBox: 0 0 2 1\n"));
        assert!(eps.contains("ffffff000000"));
        assert!(eps.trim_end().ends_with("%%EOF"));
    }

    #[test]
    fn eps_blends_transparency_over_white() {
        let mut pixmap = tiny_skia::Pixmap::new(1, 1).unwrap();
        pixmap.pixels_mut()[0] = tiny_skia::PremultipliedColorU8::from_rgba(0, 0, 0, 128).unwrap();
        let eps = String::from_utf8(encode_eps(&pixmap, 144.0)).unwrap();
        assert!(eps.contains("%%BoundingBox: 0 0 1 1\n"));
        assert!(eps.contains("7f7f7f"));
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
