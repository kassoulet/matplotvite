use ndarray::ArrayViewD;
use rayon::prelude::*;

use crate::color::Cmap;
use crate::model::{ImageItem, PngCompression};

/// Upper bound on `imshow` pixels, matching the figure-canvas budget. Without
/// it a huge array could ask `Pixmap::new` for an allocation that aborts the
/// process instead of raising a Python exception.
const MAX_IMAGE_PIXELS: usize = 1 << 26;

/// Below this size, Rayon's scheduling overhead costs more than it saves.
const PARALLEL_IMAGE_PIXELS: usize = 16_384;

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

/// Scale an 8-bit alpha channel by the constant image opacity.
fn scaled_alpha(value: f64, opacity: f64) -> u8 {
    (value * opacity.clamp(0.0, 1.0)).round().clamp(0.0, 255.0) as u8
}

/// Matplotlib's `antialiased` keeps nearest sampling until an image is shrunk
/// by more than 3x, where it filters to avoid aliasing.
fn needs_box_filter(source_width: u32, source_height: u32, width: u32, height: u32) -> bool {
    width > 0
        && height > 0
        && (source_width as f64 / width as f64 > 3.0 || source_height as f64 / height as f64 > 3.0)
}

/// Area-average a premultiplied source pixmap into the requested size.
fn resample_area(
    source: &tiny_skia::Pixmap,
    width: u32,
    height: u32,
) -> Result<tiny_skia::Pixmap, String> {
    if width == 0 || height == 0 {
        return Err("cannot resample an image to zero pixels".into());
    }
    let (sw, sh) = (source.width() as usize, source.height() as usize);
    let data = source.data();
    let stride = sw * 4;
    let mut out = tiny_skia::Pixmap::new(width, height)
        .ok_or_else(|| format!("failed to allocate {width}x{height} resampled image"))?;
    out.pixels_mut()
        .par_chunks_mut(width as usize)
        .enumerate()
        .for_each(|(y, row)| {
            let sy0 = (y as u64 * sh as u64 / height as u64) as usize;
            let sy1 = ((((y as u64 + 1) * sh as u64).div_ceil(height as u64)) as usize)
                .max(sy0 + 1)
                .min(sh);
            for (x, dst) in row.iter_mut().enumerate() {
                let sx0 = (x as u64 * sw as u64 / width as u64) as usize;
                let sx1 = ((((x as u64 + 1) * sw as u64).div_ceil(width as u64)) as usize)
                    .max(sx0 + 1)
                    .min(sw);
                let mut sums = [0u64; 4];
                for sy in sy0..sy1 {
                    for sx in sx0..sx1 {
                        let i = sy * stride + sx * 4;
                        for channel in 0..4 {
                            sums[channel] += data[i + channel] as u64;
                        }
                    }
                }
                let count = ((sy1 - sy0) * (sx1 - sx0)) as u64;
                *dst = tiny_skia::PremultipliedColorU8::from_rgba(
                    (sums[0] / count) as u8,
                    (sums[1] / count) as u8,
                    (sums[2] / count) as u8,
                    (sums[3] / count) as u8,
                )
                .expect("averaged channels are in range");
            }
        });
    Ok(out)
}

/// Convert an `imshow` array into premultiplied RGBA pixels.
pub(crate) fn image_pixmap(item: &ImageItem) -> Result<tiny_skia::Pixmap, String> {
    let (arr, cmap, vmin, vmax, _, _, opacity, _interpolation) = item;
    image_pixmap_parts(arr.as_array(), *cmap, *vmin, *vmax, *opacity)
}

/// Shared implementation for axes images and `Figure.figimage`.
pub(crate) fn image_pixmap_parts(
    a: ArrayViewD<'_, f64>,
    cmap: Cmap,
    vmin: Option<f64>,
    vmax: Option<f64>,
    opacity: f64,
) -> Result<tiny_skia::Pixmap, String> {
    let opacity = opacity.clamp(0.0, 1.0);
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
    let parallel = pixel_count >= PARALLEL_IMAGE_PIXELS;
    if let Some(src) = a.as_slice() {
        // Contiguous arrays can be walked in memory order, avoiding an
        // `a[[y, x]]` bounds check for every channel of every pixel. Large
        // images are converted a row at a time across the Rayon pool.
        if rgb {
            let channels = shape[2];
            let write_row = |dst: &mut [tiny_skia::PremultipliedColorU8], row: &[f64]| {
                for (dst, chunk) in dst.iter_mut().zip(row.chunks_exact(channels)) {
                    let ch = |i: usize| (chunk[i].clamp(0.0, 1.0) * 255.0).round() as u8;
                    let alpha = if channels == 4 {
                        scaled_alpha(ch(3) as f64, opacity)
                    } else {
                        scaled_alpha(255.0, opacity)
                    };
                    *dst = tiny_skia::ColorU8::from_rgba(ch(0), ch(1), ch(2), alpha).premultiply();
                }
            };
            if parallel {
                pixels
                    .par_chunks_mut(w)
                    .zip(src.par_chunks(w * channels))
                    .for_each(|(dst, row)| write_row(dst, row));
            } else {
                for (dst, row) in pixels.chunks_mut(w).zip(src.chunks_exact(w * channels)) {
                    write_row(dst, row);
                }
            }
        } else {
            let write_row = |dst: &mut [tiny_skia::PremultipliedColorU8], row: &[f64]| {
                for (dst, &v) in dst.iter_mut().zip(row) {
                    let c = cmap.sample((v - lo) / span);
                    let alpha = scaled_alpha(c[3] as f64, opacity);
                    *dst = tiny_skia::ColorU8::from_rgba(c[0], c[1], c[2], alpha).premultiply();
                }
            };
            if parallel {
                pixels
                    .par_chunks_mut(w)
                    .zip(src.par_chunks(w))
                    .for_each(|(dst, row)| write_row(dst, row));
            } else {
                for (dst, row) in pixels.chunks_mut(w).zip(src.chunks_exact(w)) {
                    write_row(dst, row);
                }
            }
        }
    } else {
        // Non-contiguous views keep the strided indexing path.
        for y in 0..h {
            for x in 0..w {
                let c = if rgb {
                    let ch = |i: usize| (a[[y, x, i]].clamp(0.0, 1.0) * 255.0).round() as u8;
                    let alpha = if shape[2] == 4 {
                        scaled_alpha(ch(3) as f64, opacity)
                    } else {
                        scaled_alpha(255.0, opacity)
                    };
                    [ch(0), ch(1), ch(2), alpha]
                } else {
                    let mut c = cmap.sample((a[[y, x]] - lo) / span);
                    c[3] = scaled_alpha(c[3] as f64, opacity);
                    c
                };
                pixels[y * w + x] =
                    tiny_skia::ColorU8::from_rgba(c[0], c[1], c[2], c[3]).premultiply();
            }
        }
    }
    Ok(pm)
}

/// Encode an axes image at the size it will occupy, box-filtering
/// `antialiased` images that are shrunk by more than 3x.
pub(crate) fn image_png_for_size(
    item: &ImageItem,
    width: u32,
    height: u32,
) -> Result<Vec<u8>, String> {
    let (arr, _, _, _, _, _, opacity, interpolation) = item;
    let shape = arr.as_array().shape().to_vec();
    let opaque = *opacity >= 1.0 && (shape.len() != 3 || shape[2] == 3);
    let pm = image_pixmap(item)?;
    let pm = if interpolation == "antialiased"
        && needs_box_filter(pm.width(), pm.height(), width, height)
    {
        resample_area(&pm, width, height)?
    } else {
        pm
    };
    crate::export::encode_png(&pm, PngCompression::Fast, opaque).map_err(|e| e.to_string())
}

/// Encode an image array for a `figimage` overlay.
pub(crate) fn image_png_parts(
    array: ArrayViewD<'_, f64>,
    cmap: Cmap,
    vmin: Option<f64>,
    vmax: Option<f64>,
    opacity: f64,
) -> Result<Vec<u8>, String> {
    let shape = array.shape();
    let opaque = opacity >= 1.0 && (shape.len() != 3 || shape[2] == 3);
    let pm = image_pixmap_parts(array, cmap, vmin, vmax, opacity)?;
    // The default encoder level dominates save time for full-resolution
    // images; fast compression keeps the embedded PNG cheap to produce.
    crate::export::encode_png(&pm, PngCompression::Fast, opaque).map_err(|e| e.to_string())
}

/// Flatten an image into opaque RGB at the requested size, blending its alpha
/// over the axes background. The direct bitmap path uses this instead of
/// encoding a PNG and handing it to resvg.
pub(crate) fn image_rgb(
    item: &ImageItem,
    width: u32,
    height: u32,
    background: [u8; 3],
) -> Result<Vec<u8>, String> {
    if width == 0 || height == 0 {
        return Ok(Vec::new());
    }
    let pm = image_pixmap(item)?;
    if item.7 == "antialiased" && needs_box_filter(pm.width(), pm.height(), width, height) {
        let pm = resample_area(&pm, width, height)?;
        return rgba_to_rgb(&pm, width, height, background);
    }
    rgba_to_rgb(&pm, width, height, background)
}

/// Flatten a premultiplied pixmap over the axes background at the target size.
fn rgba_to_rgb(
    pm: &tiny_skia::Pixmap,
    width: u32,
    height: u32,
    background: [u8; 3],
) -> Result<Vec<u8>, String> {
    let (sw, sh) = (pm.width(), pm.height());
    let src = pm.data();
    // The source column depends only on x, so compute it once instead of doing
    // two 64-bit divisions per output pixel.
    let columns: Vec<usize> = (0..width)
        .map(|x| (x as u64 * sw as u64 / width as u64) as usize)
        .collect();
    let mut out = vec![0u8; width as usize * height as usize * 3];
    out.par_chunks_mut(width as usize * 3)
        .enumerate()
        .for_each(|(y, row)| {
            let sy = (y as u64 * sh as u64 / height as u64) as usize;
            let src_row = sy * sw as usize * 4;
            for (x, dst) in row.as_chunks_mut::<3>().0.iter_mut().enumerate() {
                let src_i = src_row + columns[x] * 4;
                let alpha = src[src_i + 3] as u32;
                for c in 0..3 {
                    dst[c] = (src[src_i + c] as u32 + background[c] as u32 * (255 - alpha) / 255)
                        .min(255) as u8;
                }
            }
        });
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn antialiased_only_filters_when_shrinking_past_three_x() {
        assert!(!needs_box_filter(3, 3, 1, 1));
        assert!(needs_box_filter(4, 4, 1, 1));
        assert!(needs_box_filter(10, 2, 1, 2));
    }

    #[test]
    fn area_filter_blends_a_shrunk_checkerboard() {
        let mut source = tiny_skia::Pixmap::new(4, 4).unwrap();
        for (i, pixel) in source.pixels_mut().iter_mut().enumerate() {
            let v = if ((i % 4) + (i / 4)) % 2 == 0 { 255 } else { 0 };
            *pixel = tiny_skia::ColorU8::from_rgba(v, v, v, 255).premultiply();
        }
        let out = resample_area(&source, 2, 2).unwrap();
        for pixel in out.data().as_chunks::<4>().0 {
            assert!((127..=128).contains(&pixel[0]), "got {pixel:?}");
            assert_eq!(pixel[3], 255);
        }
    }
}
