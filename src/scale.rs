//! A drawing backend that renders logical pixels at an integer oversampling
//! factor. Plotters' layout code keeps working in logical coordinates while
//! every primitive is forwarded to the inner backend at `scale` times the size.

use plotters::backend::DrawingBackend;
use plotters::style::{FontDesc, TextStyle};
use plotters_backend::{
    BackendColor, BackendCoord, BackendStyle, BackendTextStyle, DrawingErrorKind,
};

pub(crate) struct ScaleBackend<DB: DrawingBackend> {
    inner: DB,
    scale: u32,
}

impl<DB: DrawingBackend> ScaleBackend<DB> {
    pub(crate) fn new(inner: DB, scale: u32) -> Self {
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
