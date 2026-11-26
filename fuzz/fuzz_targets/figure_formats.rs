#![no_main]

use libfuzzer_sys::fuzz_target;
use matplotvite::Figure;
use ndarray::Array2;

// Arbitrary text and numbers through every artist kind and every output
// format. Errors are fine; panics, hangs and aborts are not.
fuzz_target!(|data: &[u8]| {
    if data.len() < 6 {
        return;
    }
    let width = 32 + u32::from(data[0]) % 200;
    let height = 32 + u32::from(data[1]) % 200;
    let kind = data[2] % 5;
    let format = ["png", "svg", "pdf", "webp", "eps"][usize::from(data[3]) % 5];
    let split = (usize::from(data[4]) % (data.len() - 5)) + 5;
    let text = String::from_utf8_lossy(&data[split..]).into_owned();
    let values: Vec<f64> = data[5..split]
        .chunks_exact(8)
        .map(|bytes| f64::from_le_bytes(bytes.try_into().unwrap_or([0; 8])))
        .take(128)
        .collect();
    let half = values.len() / 2;
    let (x, y) = (&values[..half], &values[half..half * 2]);

    let mut figure = Figure::new(width, height);
    if let Ok(mut axes) = figure.subplot(1, 1, 0) {
        let _ = match kind {
            0 => axes.scatter(x, y).map(|_| ()),
            1 => axes.bar(x, y).map(|_| ()),
            2 => axes.hist(&values, 1 + usize::from(data[5]) % 32).map(|_| ()),
            3 => {
                let side = 1 + usize::from(data[5]) % 8;
                let grid: Vec<f64> = values.iter().copied().cycle().take(side * side).collect();
                match Array2::from_shape_vec((side, side), grid) {
                    Ok(array) if !values.is_empty() => axes.imshow(array.view()).map(|_| ()),
                    _ => Ok(()),
                }
            }
            _ => axes.plot(x, y).map(|_| ()),
        };
        axes.text(0.5, 0.5, text.clone());
        axes.label(text);
    }
    let _ = figure.to_bytes(format);
});
