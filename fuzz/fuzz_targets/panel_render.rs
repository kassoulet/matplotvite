#![no_main]

use _core::Figure;
use libfuzzer_sys::fuzz_target;

// The Python facade turns a panel into PyO3 records before rendering. This
// target exercises the same public panel builder and renderer without needing a
// live Python interpreter, so arbitrary numeric payloads reach the drawing
// pipeline.
fuzz_target!(|data: &[u8]| {
    if data.len() < 3 {
        return;
    }
    let width = 64 + u32::from(data[0]) % 256;
    let height = 64 + u32::from(data[1]) % 256;
    let values: Vec<f64> = data[2..]
        .chunks_exact(8)
        .map(|bytes| f64::from_le_bytes(bytes.try_into().expect("chunk is eight bytes")))
        .filter(|value| value.is_finite())
        .take(256)
        .collect();
    if values.len() < 2 {
        return;
    }

    let half = values.len() / 2;
    let (x, y) = (&values[..half], &values[half..half * 2]);
    let mut figure = Figure::new(width, height);
    {
        if let Ok(mut axes) = figure.subplot(1, 1, 0) {
            let _ = axes.plot(x, y);
        }
    }
    let _ = figure.to_bytes("png");
});
