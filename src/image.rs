use crate::color::colormap;
use crate::model::ImageItem;

/// Upper bound on `imshow` pixels, matching the figure-canvas budget. Without
/// it a huge array could ask `Pixmap::new` for an allocation that aborts the
/// process instead of raising a Python exception.
const MAX_IMAGE_PIXELS: usize = 1 << 28;

pub(crate) fn base64(data: &[u8]) -> String {
    const T: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(data.len().div_ceil(3) * 4);
    for chunk in data.chunks(3) {
        let b = [
            chunk[0],
            *chunk.get(1).unwrap_or(&0),
            *chunk.get(2).unwrap_or(&0),
        ];
        let n = ((b[0] as u32) << 16) | ((b[1] as u32) << 8) | b[2] as u32;
        out.push(T[(n >> 18) as usize & 63] as char);
        out.push(T[(n >> 12) as usize & 63] as char);
        out.push(if chunk.len() > 1 {
            T[(n >> 6) as usize & 63] as char
        } else {
            '='
        });
        out.push(if chunk.len() > 2 {
            T[n as usize & 63] as char
        } else {
            '='
        });
    }
    out
}

/// Encode an `imshow` array as a PNG: 2-D through the colormap, 3-D as RGB(A).
pub(crate) fn image_png(item: &ImageItem) -> Result<Vec<u8>, String> {
    let (arr, cmap, vmin, vmax, _, _) = item;
    let a = arr.as_array();
    let shape = a.shape();
    let (h, w) = match shape {
        [h, w] => (*h, *w),
        [h, w, c] if *c == 3 || *c == 4 => (*h, *w),
        _ => return Err("imshow expects a 2-D array or an (H, W, 3|4) RGB(A) array".into()),
    };
    if h == 0 || w == 0 {
        return Err("imshow got an empty array".into());
    }
    let pixel_count = h
        .checked_mul(w)
        .ok_or_else(|| format!("imshow dimensions {h}x{w} overflow"))?;
    if pixel_count > MAX_IMAGE_PIXELS {
        return Err(format!(
            "imshow image has {pixel_count} pixels, maximum allowed is {MAX_IMAGE_PIXELS}"
        ));
    }
    let width = u32::try_from(w)
        .map_err(|_| format!("imshow width {w} exceeds the maximum of {}", u32::MAX))?;
    let height = u32::try_from(h)
        .map_err(|_| format!("imshow height {h} exceeds the maximum of {}", u32::MAX))?;
    let rgb = shape.len() == 3;
    let (lo, hi) = if rgb {
        (0.0, 1.0)
    } else {
        let mut lo = f64::MAX;
        let mut hi = f64::MIN;
        for v in a.iter().copied().filter(|v| v.is_finite()) {
            lo = lo.min(v);
            hi = hi.max(v);
        }
        if lo > hi {
            (0.0, 1.0)
        } else {
            (vmin.unwrap_or(lo), vmax.unwrap_or(hi))
        }
    };
    let span = if hi > lo { hi - lo } else { 1.0 };
    let mut pm = tiny_skia::Pixmap::new(width, height).ok_or("failed to allocate image")?;
    let pixels = pm.pixels_mut();
    if let Some(src) = a.as_slice() {
        // Contiguous arrays can be walked in memory order, avoiding an
        // `a[[y, x]]` bounds check for every channel of every pixel.
        if rgb {
            let channels = shape[2];
            for (dst, chunk) in pixels.iter_mut().zip(src.chunks_exact(channels)) {
                let ch = |i: usize| (chunk[i].clamp(0.0, 1.0) * 255.0).round() as u8;
                let alpha = if channels == 4 { ch(3) } else { 255 };
                *dst = tiny_skia::ColorU8::from_rgba(ch(0), ch(1), ch(2), alpha).premultiply();
            }
        } else {
            for (dst, &v) in pixels.iter_mut().zip(src) {
                let c = colormap(cmap, (v - lo) / span);
                *dst = tiny_skia::ColorU8::from_rgba(c[0], c[1], c[2], c[3]).premultiply();
            }
        }
    } else {
        // Non-contiguous views keep the strided indexing path.
        for y in 0..h {
            for x in 0..w {
                let c = if rgb {
                    let ch = |i: usize| (a[[y, x, i]].clamp(0.0, 1.0) * 255.0).round() as u8;
                    let alpha = if shape[2] == 4 { ch(3) } else { 255 };
                    [ch(0), ch(1), ch(2), alpha]
                } else {
                    colormap(cmap, (a[[y, x]] - lo) / span)
                };
                pixels[y * w + x] =
                    tiny_skia::ColorU8::from_rgba(c[0], c[1], c[2], c[3]).premultiply();
            }
        }
    }
    pm.encode_png().map_err(|e| e.to_string())
}
