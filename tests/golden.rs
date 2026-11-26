//! Golden-image parity between the native builder and the Python facade.
//!
//! The scenes and tolerance live in `tests/golden/scenes.txt`, which the Python
//! suite reads too; both render the same names and compare against the committed
//! PNGs.
#![allow(clippy::unwrap_used, clippy::expect_used)] // test helpers fail loudly

use std::path::{Path, PathBuf};

use matplotvite::{Axes, Figure, GridOptions, LegendOptions, TickParams};
use ndarray::array;

const MANIFEST: &str = include_str!("golden/scenes.txt");

struct Scene {
    name: &'static str,
    width: u32,
    height: u32,
    max_rms: f64,
}

fn scenes() -> Vec<Scene> {
    MANIFEST
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .map(|line| {
            let mut fields = line.split_whitespace();
            let name = fields.next().expect("scene name");
            let width = fields.next().expect("scene width").parse().expect("width");
            let height = fields
                .next()
                .expect("scene height")
                .parse()
                .expect("height");
            let max_rms = fields.next().expect("scene rms").parse().expect("rms");
            Scene {
                name,
                width,
                height,
                max_rms,
            }
        })
        .collect()
}

fn build(scene: &Scene) -> Figure {
    let mut figure = Figure::new(scene.width, scene.height);
    match scene.name {
        "line_legend" => {
            let mut axes = figure.subplot(1, 1, 0).unwrap();
            line_legend(&mut axes);
        }
        "bars_scatter" => {
            let mut axes = figure.subplot(1, 1, 0).unwrap();
            bars_scatter(&mut axes);
        }
        "image_colorbar" => {
            let mut axes = figure.subplot(1, 1, 0).unwrap();
            image_colorbar(&mut axes);
        }
        "fill_annotate" => {
            let mut axes = figure.subplot(1, 1, 0).unwrap();
            fill_annotate(&mut axes);
        }
        other => panic!("no Rust builder for golden scene {other}"),
    }
    figure
}

fn line_legend(axes: &mut Axes<'_>) {
    axes.plot(&[0.0, 1.0, 2.0], &[0.0, 1.0, 4.0])
        .unwrap()
        .label("quadratic");
    axes.plot(&[0.0, 1.0, 2.0], &[1.0, 0.0, 1.0])
        .unwrap()
        .color("#d62728")
        .label("wave");
    axes.title("Line and legend").xlabel("x").ylabel("y");
    axes.xticks(&[0.0, 0.5, 1.0, 1.5, 2.0]);
    axes.yticks(&[0.0, 1.0, 2.0, 3.0, 4.0]);
    axes.grid_options(&GridOptions {
        show: true,
        alpha: Some(0.4),
        ..Default::default()
    });
    axes.legend_options(&LegendOptions {
        loc: "upper left".to_string(),
        ..Default::default()
    });
}

fn bars_scatter(axes: &mut Axes<'_>) {
    axes.bar(&[0.0, 1.0, 2.0], &[3.0, 5.0, 2.0])
        .unwrap()
        .color("#2ca02c")
        .label("counts");
    axes.scatter(&[0.2, 1.2, 2.2], &[4.0, 2.0, 3.0])
        .unwrap()
        .color("#ff7f0e")
        .label("points");
    axes.xticks_with_labels(&[0.0, 1.0, 2.0], &["alpha", "beta", "gamma"])
        .unwrap();
    axes.xtick_params(&TickParams {
        rotation: 30.0,
        ..Default::default()
    });
    axes.ylim(0.0, 6.0).legend().title("Bars and scatter");
}

fn image_colorbar(axes: &mut Axes<'_>) {
    axes.imshow_cmap(
        array![
            [0.0, 1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0, 7.0],
            [8.0, 9.0, 10.0, 11.0]
        ]
        .view(),
        "magma",
        Some(0.0),
        Some(11.0),
    )
    .unwrap();
    axes.xticks(&[0.0, 1.0, 2.0, 3.0]);
    axes.yticks(&[0.0, 1.0, 2.0]);
    axes.colorbar("magma", 0.0, 11.0);
}

fn fill_annotate(axes: &mut Axes<'_>) {
    let x = [0.0, 1.0, 2.0, 3.0];
    axes.fill_between(&x, &[0.0, 0.0, 0.0, 0.0], &[1.0, 2.0, 1.5, 2.0])
        .unwrap()
        .color("#9467bd")
        .alpha(0.3)
        .label("band");
    axes.plot(&x, &[0.5, 1.0, 0.8, 1.2])
        .unwrap()
        .color("#1f77b4")
        .label("mean");
    axes.text_styled(0.2, 1.8, "band", 11.0, "black", ("left", "baseline"));
    axes.annotate("peak", (1.0, 2.0), Some((1.8, 2.3)));
    axes.xlim(0.0, 3.0).ylim(0.0, 2.5);
    axes.xticks(&[0.0, 1.0, 2.0, 3.0]);
    axes.yticks(&[0.0, 0.5, 1.0, 1.5, 2.0, 2.5]);
    axes.legend_options(&LegendOptions {
        loc: "lower right".to_string(),
        ..Default::default()
    });
}

fn decode_rgba(bytes: &[u8]) -> (u32, u32, Vec<u8>) {
    let decoder = png::Decoder::new(std::io::Cursor::new(bytes));
    let mut reader = decoder.read_info().expect("valid PNG");
    let mut buffer = vec![0; reader.output_buffer_size().expect("PNG buffer")];
    let info = reader.next_frame(&mut buffer).expect("PNG frame");
    buffer.truncate(info.buffer_size());
    let rgba = match info.color_type {
        png::ColorType::Rgba => buffer,
        other => panic!("expected RGBA golden images, got {other:?}"),
    };
    (info.width, info.height, rgba)
}

fn rms(a: &[u8], b: &[u8]) -> f64 {
    let total: f64 = a
        .iter()
        .zip(b)
        .map(|(&left, &right)| {
            let diff = f64::from(left) - f64::from(right);
            diff * diff
        })
        .sum();
    (total / a.len() as f64).sqrt()
}

#[test]
fn native_builder_matches_shared_goldens() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join("tests")
        .join("golden");
    for scene in scenes() {
        let golden = root.join(format!("{}.png", scene.name));
        assert!(
            Path::new(&golden).exists(),
            "missing golden {}; run tests/golden_scenes.py",
            golden.display()
        );
        let expected = std::fs::read(&golden).expect("read golden");
        let (width, height, expected) = decode_rgba(&expected);
        assert_eq!(
            (width, height),
            (scene.width, scene.height),
            "{}: golden size",
            scene.name
        );

        let rendered = build(&scene)
            .to_bytes("png")
            .unwrap_or_else(|error| panic!("{}: {error}", scene.name));
        let (width, height, actual) = decode_rgba(&rendered);
        assert_eq!(
            (width, height),
            (scene.width, scene.height),
            "{}: rendered size",
            scene.name
        );
        let error = rms(&expected, &actual);
        assert!(
            error <= scene.max_rms,
            "{}: rms {error:.3} > {}; regenerate the golden if the change is intentional",
            scene.name,
            scene.max_rms
        );
    }
}
