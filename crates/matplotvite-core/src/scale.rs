//! Axis scale transforms plus a drawing backend that renders logical pixels at
//! an integer oversampling factor. Plotters' layout code keeps working in
//! logical coordinates while every primitive is forwarded to the inner backend
//! at `scale` times the size.

use plotters::backend::DrawingBackend;
use plotters::style::{FontDesc, TextStyle};
use plotters_backend::{
    BackendColor, BackendCoord, BackendStyle, BackendTextStyle, DrawingErrorKind,
};

/// Symmetric-log transform used by `symlog` axes.
///
/// Matplotlib's transform is linear inside `±linthresh` (scaled by
/// `linscale / (1 - 1/base)`) and logarithmic outside it.
pub fn symlog(value: f64, linthresh: f64, base: f64, linscale: f64) -> f64 {
    let l = if linthresh > 0.0 { linthresh } else { 1.0 };
    let base = if base > 1.0 { base } else { 10.0 };
    let linscale = if linscale > 0.0 { linscale } else { 1.0 };
    let adjust = linscale / (1.0 - 1.0 / base);
    if value.abs() <= l {
        value * adjust
    } else {
        value.signum() * l * (adjust + (value.abs() / l).ln() / base.ln())
    }
}

pub fn symlog_inverse(value: f64, linthresh: f64, base: f64, linscale: f64) -> f64 {
    let l = if linthresh > 0.0 { linthresh } else { 1.0 };
    let base = if base > 1.0 { base } else { 10.0 };
    let linscale = if linscale > 0.0 { linscale } else { 1.0 };
    let adjust = linscale / (1.0 - 1.0 / base);
    if value.abs() <= l * adjust {
        value / adjust
    } else {
        value.signum() * l * base.powf(value.abs() / l - adjust)
    }
}

/// Base-10 logit transform for probability axes, with Matplotlib's clipping.
pub fn logit(value: f64) -> f64 {
    if value <= 0.0 {
        -1000.0
    } else if value >= 1.0 {
        1000.0
    } else {
        (value / (1.0 - value)).log10()
    }
}

pub fn logit_inverse(value: f64) -> f64 {
    let exp = 10f64.powf(-value);
    1.0 / (1.0 + exp)
}

/// Asinh transform: linear near zero and logarithmic for large magnitudes.
pub fn asinh_scale(value: f64, linear_width: f64) -> f64 {
    let w = if linear_width > 0.0 {
        linear_width
    } else {
        1.0
    };
    w * (value / w).asinh()
}

pub fn asinh_inverse(value: f64, linear_width: f64) -> f64 {
    let w = if linear_width > 0.0 {
        linear_width
    } else {
        1.0
    };
    w * (value / w).sinh()
}

pub struct ScaleBackend<DB: DrawingBackend> {
    inner: DB,
    scale: u32,
}

impl<DB: DrawingBackend> ScaleBackend<DB> {
    pub fn new(inner: DB, scale: u32) -> Self {
        Self {
            inner,
            scale: scale.max(1),
        }
    }

    fn coord(&self, (x, y): BackendCoord) -> BackendCoord {
        (
            x.saturating_mul(self.scale as i32),
            y.saturating_mul(self.scale as i32),
        )
    }
}

/// A shape style with the same colour and a physically scaled stroke width.
struct ScaledStyle<'a, S: BackendStyle> {
    inner: &'a S,
    scale: u32,
}

impl<S: BackendStyle> BackendStyle for ScaledStyle<'_, S> {
    fn color(&self) -> BackendColor {
        self.inner.color()
    }

    fn stroke_width(&self) -> u32 {
        self.inner.stroke_width().max(1).saturating_mul(self.scale)
    }
}

/// Rebuild a text style at the physical font size. The family borrows from the
/// original style, which is exactly as long as the forwarded draw call.
fn scaled_text<'a, T: BackendTextStyle>(style: &'a T, scale: u32) -> TextStyle<'a> {
    let font = FontDesc::new(style.family(), style.size() * scale as f64, style.style())
        .transform(style.transform());
    TextStyle {
        font,
        color: style.color(),
        pos: style.anchor(),
    }
}

impl<DB: DrawingBackend> DrawingBackend for ScaleBackend<DB> {
    type ErrorType = DB::ErrorType;

    fn get_size(&self) -> (u32, u32) {
        let (w, h) = self.inner.get_size();
        (w / self.scale, h / self.scale)
    }

    fn ensure_prepared(&mut self) -> Result<(), DrawingErrorKind<Self::ErrorType>> {
        self.inner.ensure_prepared()
    }

    fn present(&mut self) -> Result<(), DrawingErrorKind<Self::ErrorType>> {
        self.inner.present()
    }

    fn draw_pixel(
        &mut self,
        point: BackendCoord,
        color: BackendColor,
    ) -> Result<(), DrawingErrorKind<Self::ErrorType>> {
        let (x, y) = self.coord(point);
        for dy in 0..self.scale as i32 {
            for dx in 0..self.scale as i32 {
                self.inner.draw_pixel((x + dx, y + dy), color)?;
            }
        }
        Ok(())
    }

    fn draw_line<S: BackendStyle>(
        &mut self,
        from: BackendCoord,
        to: BackendCoord,
        style: &S,
    ) -> Result<(), DrawingErrorKind<Self::ErrorType>> {
        self.inner.draw_line(
            self.coord(from),
            self.coord(to),
            &ScaledStyle {
                inner: style,
                scale: self.scale,
            },
        )
    }

    fn draw_rect<S: BackendStyle>(
        &mut self,
        upper_left: BackendCoord,
        bottom_right: BackendCoord,
        style: &S,
        fill: bool,
    ) -> Result<(), DrawingErrorKind<Self::ErrorType>> {
        self.inner.draw_rect(
            self.coord(upper_left),
            self.coord(bottom_right),
            &ScaledStyle {
                inner: style,
                scale: self.scale,
            },
            fill,
        )
    }

    fn draw_path<S: BackendStyle, I: IntoIterator<Item = BackendCoord>>(
        &mut self,
        path: I,
        style: &S,
    ) -> Result<(), DrawingErrorKind<Self::ErrorType>> {
        let path: Vec<BackendCoord> = path.into_iter().map(|point| self.coord(point)).collect();
        self.inner.draw_path(
            path,
            &ScaledStyle {
                inner: style,
                scale: self.scale,
            },
        )
    }

    fn draw_circle<S: BackendStyle>(
        &mut self,
        center: BackendCoord,
        radius: u32,
        style: &S,
        fill: bool,
    ) -> Result<(), DrawingErrorKind<Self::ErrorType>> {
        self.inner.draw_circle(
            self.coord(center),
            radius.saturating_mul(self.scale),
            &ScaledStyle {
                inner: style,
                scale: self.scale,
            },
            fill,
        )
    }

    fn fill_polygon<S: BackendStyle, I: IntoIterator<Item = BackendCoord>>(
        &mut self,
        vert: I,
        style: &S,
    ) -> Result<(), DrawingErrorKind<Self::ErrorType>> {
        let vert: Vec<BackendCoord> = vert.into_iter().map(|point| self.coord(point)).collect();
        self.inner.fill_polygon(
            vert,
            &ScaledStyle {
                inner: style,
                scale: self.scale,
            },
        )
    }

    fn draw_text<TStyle: BackendTextStyle>(
        &mut self,
        text: &str,
        style: &TStyle,
        pos: BackendCoord,
    ) -> Result<(), DrawingErrorKind<Self::ErrorType>> {
        let style = scaled_text(style, self.scale);
        self.inner.draw_text(text, &style, self.coord(pos))
    }

    fn estimate_text_size<TStyle: BackendTextStyle>(
        &self,
        text: &str,
        style: &TStyle,
    ) -> Result<(u32, u32), DrawingErrorKind<Self::ErrorType>> {
        let style = scaled_text(style, self.scale);
        self.inner
            .estimate_text_size(text, &style)
            .map(|(w, h)| (w.div_ceil(self.scale), h.div_ceil(self.scale)))
    }

    fn blit_bitmap(
        &mut self,
        pos: BackendCoord,
        (iw, ih): (u32, u32),
        src: &[u8],
    ) -> Result<(), DrawingErrorKind<Self::ErrorType>> {
        let (dw, dh) = (iw.saturating_mul(self.scale), ih.saturating_mul(self.scale));
        let mut scaled = Vec::with_capacity(dw as usize * dh as usize * 3);
        for y in 0..dh {
            let sy = y / self.scale;
            for x in 0..dw {
                let sx = x / self.scale;
                let offset = (sy * iw + sx) as usize * 3;
                scaled.extend_from_slice(&src[offset..offset + 3]);
            }
        }
        self.inner.blit_bitmap(self.coord(pos), (dw, dh), &scaled)
    }
}

#[cfg(test)]
mod tests {
    use super::{asinh_inverse, asinh_scale, logit, logit_inverse, symlog, symlog_inverse};
    use proptest::prelude::*;

    #[test]
    fn asinh_is_linear_near_zero_and_inverts() {
        assert!((asinh_scale(0.0, 2.0)).abs() < 1e-12);
        assert!((asinh_scale(1.0, 1.0) - (1.0_f64).asinh()).abs() < 1e-12);
        assert!((asinh_scale(2.0, 2.0) - 2.0 * (1.0_f64).asinh()).abs() < 1e-12);
        assert!((asinh_inverse(asinh_scale(12.0, 0.5), 0.5) - 12.0).abs() < 1e-9);
    }

    #[test]
    fn symlog_is_linear_inside_and_logarithmic_outside() {
        let adjust = 1.0 / (1.0 - 1.0 / 10.0);
        assert!((symlog(0.5, 1.0, 10.0, 1.0) - 0.5 * adjust).abs() < 1e-12);
        assert!((symlog(1000.0, 1.0, 10.0, 1.0) - (adjust + 3.0)).abs() < 1e-12);
        for value in [-1000.0, -1.0, -0.5, 0.0, 0.5, 1.0, 1000.0] {
            let round_trip = symlog_inverse(symlog(value, 1.0, 10.0, 1.0), 1.0, 10.0, 1.0);
            assert!((round_trip - value).abs() < 1e-9, "{value} -> {round_trip}");
        }
    }

    #[test]
    fn logit_maps_probabilities_and_clamps_endpoints() {
        assert!((logit(0.5) - 0.0).abs() < 1e-12);
        assert!((logit(0.75) - 3.0_f64.log10()).abs() < 1e-12);
        assert_eq!(logit(0.0), -1000.0);
        assert_eq!(logit(1.0), 1000.0);
        assert!((logit_inverse(logit(0.75)) - 0.75).abs() < 1e-12);
    }

    proptest! {
        #[test]
        fn symlog_round_trips_finite_inputs(
            value in -1e9f64..1e9f64,
            linthresh in 1e-6f64..1e6f64,
            base in 1.1f64..1000.0f64,
            linscale in 0.01f64..100.0f64,
        ) {
            let transformed = symlog(value, linthresh, base, linscale);
            let restored = symlog_inverse(transformed, linthresh, base, linscale);
            prop_assert!((restored - value).abs() <= 1e-6 * value.abs().max(1.0));
        }

        #[test]
        fn logit_round_trips_interior_probabilities(value in 1e-6f64..0.999999f64) {
            let restored = logit_inverse(logit(value));
            prop_assert!((restored - value).abs() <= 1e-9 * value.abs().max(1.0));
        }

        #[test]
        fn asinh_round_trips_finite_inputs(
            value in -1e9f64..1e9f64,
            width in 1e-6f64..1e6f64,
        ) {
            let restored = asinh_inverse(asinh_scale(value, width), width);
            prop_assert!((restored - value).abs() <= 1e-8 * value.abs().max(1.0));
        }
    }
}

#[cfg(test)]
mod backend_tests {
    use super::ScaleBackend;
    use plotters::backend::{BitMapBackend, SVGBackend};
    use plotters::prelude::*;
    use plotters::style::{IntoFont, ShapeStyle};
    use plotters_backend::BackendColor;

    const RED: BackendColor = BackendColor {
        alpha: 1.0,
        rgb: (255, 0, 0),
    };

    fn style() -> ShapeStyle {
        ShapeStyle {
            color: RGBAColor(255, 0, 0, 1.0),
            filled: true,
            stroke_width: 1,
        }
    }

    #[test]
    fn a_pixel_becomes_an_oversampled_block() {
        let mut buf = vec![255u8; 32 * 32 * 3];
        {
            let mut backend = ScaleBackend::new(BitMapBackend::with_buffer(&mut buf, (32, 32)), 2);
            assert_eq!(backend.get_size(), (16, 16));
            backend.ensure_prepared().unwrap();
            backend.draw_pixel((1, 1), RED).unwrap();
            backend.present().unwrap();
        }
        for (x, y) in [(2, 2), (3, 2), (2, 3), (3, 3)] {
            let i = ((y * 32 + x) * 3) as usize;
            assert_eq!(&buf[i..i + 3], &[255, 0, 0], "pixel ({x}, {y})");
        }
        let untouched = (32 + 1) * 3;
        assert_eq!(&buf[untouched..untouched + 3], &[255, 255, 255]);
    }

    #[test]
    fn every_drawing_call_is_forwarded_at_scale_times_the_coordinate() {
        let mut buf = vec![255u8; 32 * 32 * 3];
        {
            let mut backend = ScaleBackend::new(BitMapBackend::with_buffer(&mut buf, (32, 32)), 2);
            let style = style();
            backend.draw_line((0, 0), (15, 15), &style).unwrap();
            backend.draw_rect((2, 2), (6, 6), &style, true).unwrap();
            backend
                .draw_path(vec![(1, 14), (8, 8), (14, 1)], &style)
                .unwrap();
            backend.draw_circle((8, 8), 3, &style, false).unwrap();
            backend
                .fill_polygon(vec![(0, 0), (10, 0), (10, 10)], &style)
                .unwrap();
            // A 2x2 source bitmap becomes a 4x4 block: the first two device
            // columns come from source column 0, the next two from column 1.
            let src = [1u8, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
            backend.blit_bitmap((10, 10), (2, 2), &src).unwrap();
            backend.present().unwrap();
        }
        assert!(buf
            .as_chunks::<3>()
            .0
            .iter()
            .any(|pixel| *pixel != [255, 255, 255]));
        let at = |x: usize, y: usize| {
            let i = (y * 32 + x) * 3;
            [buf[i], buf[i + 1], buf[i + 2]]
        };
        assert_eq!(at(20, 20), [1, 2, 3]);
        assert_eq!(at(22, 20), [4, 5, 6]);
        assert_eq!(at(23, 23), [10, 11, 12]);
    }

    #[test]
    fn text_is_measured_and_drawn_at_the_scaled_font_size() {
        let render = |scale: u32| {
            let mut svg = String::new();
            {
                let backend =
                    ScaleBackend::new(SVGBackend::with_string(&mut svg, (100, 50)), scale);
                let area = backend.into_drawing_area();
                area.draw(&Text::new("hi", (5, 5), ("sans-serif", 10u32).into_font()))
                    .unwrap();
                area.present().unwrap();
            }
            svg
        };
        let logical = render(1);
        let oversampled = render(3);
        assert!(logical.contains("hi"), "{logical}");
        assert!(oversampled.contains("hi"), "{oversampled}");
        assert_ne!(logical, oversampled);
    }
}
