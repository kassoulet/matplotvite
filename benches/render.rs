use std::fmt::Write as _;
use std::hint::black_box;
use std::time::Duration;

use _core::bench;
use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};

fn svg_fixture(width: u32, height: u32) -> String {
    let mut svg = String::new();
    write!(
        svg,
        r#"<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">"#
    )
    .unwrap();
    svg.push_str(r##"<rect width="100%" height="100%" fill="#ffffff"/>"##);

    for i in 0..24 {
        let y = 24.0 + i as f64 * (height as f64 - 48.0) / 23.0;
        write!(
            svg,
            r##"<line x1="52" y1="{y:.2}" x2="{}" y2="{y:.2}" stroke="#e4e8ef" stroke-width="0.7"/>"##,
            width - 24
        )
        .unwrap();
    }

    for series in 0..18 {
        let phase = series as f64 * 0.35;
        let amplitude = 0.18 + (series % 5) as f64 * 0.025;
        write!(
            svg,
            r##"<polyline fill="none" stroke="#1f4e79" stroke-width="1.1" points=""##
        )
        .unwrap();
        for sample in 0..180 {
            let t = sample as f64 / 179.0;
            let x = 52.0 + t * (width as f64 - 76.0);
            let y = height as f64 * (0.5 - amplitude * (t * 12.0 + phase).sin());
            write!(svg, "{x:.2},{y:.2} ").unwrap();
        }
        svg.push_str(r##""/>"##);
    }

    for i in 0..12 {
        let x = 52.0 + i as f64 * (width as f64 - 76.0) / 11.0;
        write!(
            svg,
            r##"<text x="{x:.2}" y="{}" font-family="Geist" font-size="9" fill="#5d6b7e">{i}</text>"##,
            height - 18
        )
        .unwrap();
    }
    svg.push_str("</svg>");
    svg
}

/// One polyline with `points` vertices — the shape a dense line series emits.
fn dense_line_svg(width: u32, height: u32, points: usize) -> String {
    let mut svg = String::new();
    write!(
        svg,
        r#"<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">"#
    )
    .unwrap();
    svg.push_str(r##"<rect width="100%" height="100%" fill="#ffffff"/>"##);
    svg.push_str(r##"<polyline fill="none" stroke="#1f4e79" stroke-width="1.1" points=""##);
    for sample in 0..points {
        let t = sample as f64 / (points - 1) as f64;
        let x = 40.0 + t * (width as f64 - 60.0);
        let y = height as f64 * (0.5 - 0.4 * (t * 400.0).sin());
        write!(svg, "{x:.2},{y:.2} ").unwrap();
    }
    svg.push_str(r##""/></svg>"##);
    svg
}

/// A grid of filled cells split into triangles — the shape a filled contour
/// panel emits before cells are merged into runs.
fn filled_grid_svg(width: u32, height: u32, cells_per_side: usize) -> String {
    let mut svg = String::new();
    write!(
        svg,
        r#"<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">"#
    )
    .unwrap();
    svg.push_str(r##"<rect width="100%" height="100%" fill="#ffffff"/>"##);
    let cell_w = (width as f64 - 80.0) / cells_per_side as f64;
    let cell_h = (height as f64 - 60.0) / cells_per_side as f64;
    for row in 0..cells_per_side {
        for col in 0..cells_per_side {
            let x = 40.0 + col as f64 * cell_w;
            let y = 30.0 + row as f64 * cell_h;
            let t = (row + col) as f64 / (cells_per_side * 2) as f64;
            let color = if t < 0.5 { "#440154" } else { "#fde725" };
            write!(
                svg,
                r##"<polygon fill="{color}" points="{x:.2},{y:.2} {:.2},{y:.2} {:.2},{:.2} "/>"##,
                x + cell_w,
                x + cell_w,
                y + cell_h
            )
            .unwrap();
            write!(
                svg,
                r##"<polygon fill="{color}" points="{x:.2},{y:.2} {:.2},{:.2} {x:.2},{:.2} "/>"##,
                x + cell_w,
                y + cell_h,
                y + cell_h
            )
            .unwrap();
        }
    }
    svg.push_str("</svg>");
    svg
}

fn pixmap_fixture(width: u32, height: u32) -> tiny_skia::Pixmap {
    let mut pixmap = tiny_skia::Pixmap::new(width, height).unwrap();
    let data = pixmap.data_mut();
    for y in 0..height {
        for x in 0..width {
            let offset = ((y * width + x) * 4) as usize;
            let wave = ((x as f64 * 0.04).sin() * (y as f64 * 0.03).cos() * 64.0 + 160.0) as u8;
            data[offset] = wave;
            data[offset + 1] = wave / 2 + 40;
            data[offset + 2] = 255 - wave;
            data[offset + 3] = 255;
        }
    }
    pixmap
}

fn rasterize(c: &mut Criterion) {
    let mut group = c.benchmark_group("rasterize_svg");
    for (width, height) in [(640, 480), (1280, 720), (1920, 1080)] {
        let svg = svg_fixture(width, height);
        group.throughput(Throughput::Bytes(svg.len() as u64));
        group.bench_with_input(
            BenchmarkId::from_parameter(format!("{width}x{height}")),
            &svg,
            |b, svg| {
                b.iter(|| {
                    bench::rasterize_svg(black_box(svg), black_box(width), black_box(height))
                        .unwrap()
                })
            },
        );
    }
    group.finish();
}

fn rasterize_dense(c: &mut Criterion) {
    let mut group = c.benchmark_group("rasterize_dense_line");
    for points in [10_000, 50_000, 100_000] {
        let svg = dense_line_svg(640, 480, points);
        group.throughput(Throughput::Bytes(svg.len() as u64));
        group.bench_with_input(
            BenchmarkId::from_parameter(format!("{points}_points")),
            &svg,
            |b, svg| {
                b.iter(|| {
                    bench::rasterize_svg(black_box(svg), black_box(640), black_box(480)).unwrap()
                })
            },
        );
    }
    group.finish();
}

fn rasterize_filled(c: &mut Criterion) {
    let mut group = c.benchmark_group("rasterize_filled_grid");
    for cells in [64, 128, 160] {
        let svg = filled_grid_svg(640, 480, cells);
        group.throughput(Throughput::Bytes(svg.len() as u64));
        group.bench_with_input(
            BenchmarkId::from_parameter(format!("{cells}x{cells}")),
            &svg,
            |b, svg| {
                b.iter(|| {
                    bench::rasterize_svg(black_box(svg), black_box(640), black_box(480)).unwrap()
                })
            },
        );
    }
    group.finish();
}

fn encode_png(c: &mut Criterion) {
    let mut group = c.benchmark_group("encode_png");
    for (width, height) in [(640, 480), (1280, 720), (1920, 1080)] {
        let pixmap = pixmap_fixture(width, height);
        group.throughput(Throughput::Bytes((width * height * 4) as u64));
        for compression in ["fast", "default", "best"] {
            group.bench_with_input(
                BenchmarkId::new(compression, format!("{width}x{height}")),
                &pixmap,
                |b, pixmap| {
                    // Gallery output is opaque, so the encoder can read the
                    // buffer directly without demultiplying a copy.
                    b.iter(|| {
                        bench::encode_png_bytes(black_box(pixmap), black_box(compression), true)
                            .unwrap()
                    })
                },
            );
        }
    }
    group.finish();
}

fn encode_webp(c: &mut Criterion) {
    let mut group = c.benchmark_group("encode_webp");
    for (width, height) in [(640, 480), (1280, 720), (1920, 1080)] {
        let pixmap = pixmap_fixture(width, height);
        group.throughput(Throughput::Bytes((width * height * 4) as u64));
        group.bench_with_input(
            BenchmarkId::from_parameter(format!("{width}x{height}")),
            &pixmap,
            |b, pixmap| b.iter(|| bench::encode_webp_bytes(black_box(pixmap)).unwrap()),
        );
    }
    group.finish();
}

fn encode_pdf(c: &mut Criterion) {
    let mut group = c.benchmark_group("encode_pdf");
    for (width, height) in [(640, 480), (1280, 720)] {
        let svg = svg_fixture(width, height);
        group.throughput(Throughput::Bytes(svg.len() as u64));
        group.bench_with_input(
            BenchmarkId::from_parameter(format!("{width}x{height}")),
            &svg,
            |b, svg| {
                b.iter(|| bench::svg_to_pdf(black_box(svg), 100.0, (width, height), false).unwrap())
            },
        );
    }
    group.finish();
}

criterion_group! {
    name = benches;
    config = Criterion::default()
        .sample_size(20)
        .warm_up_time(Duration::from_secs(1))
        .measurement_time(Duration::from_secs(3))
        .without_plots();
    targets = rasterize, rasterize_dense, rasterize_filled, encode_png, encode_webp, encode_pdf
}
criterion_main!(benches);
