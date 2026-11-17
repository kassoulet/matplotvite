//! Marker geometry and marker rendering.

use super::*;

/// Largest marker radius drawn; a bad `s` value should not ask the backend
/// to build an arbitrarily large path.
pub(super) const MAX_MARKER_RADIUS: f64 = 4096.0;

pub(super) fn marker_radius(area: f64) -> f64 {
    (area.max(0.0).sqrt() / 2.0 * 1.39).clamp(1.0, MAX_MARKER_RADIUS)
}

/// Marker geometry in matplotlib's normalized unit square (y up): filled
/// outlines as polygons, stroked markers as line subpaths, circles by radius.
enum MarkerShape {
    Polygon(Vec<(f64, f64)>),
    Strokes(Vec<((f64, f64), (f64, f64))>),
    Circle(f64),
}

/// matplotlib's marker paths, so markers we draw match its shapes exactly.
fn marker_shape(marker: Marker) -> MarkerShape {
    let poly = |pts: &[(f64, f64)]| MarkerShape::Polygon(pts.to_vec());
    match marker {
        Marker::Square => poly(&[(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]),
        Marker::Diamond => poly(&[(0.0, -0.5), (0.5, 0.0), (0.0, 0.5), (-0.5, 0.0)]),
        Marker::ThinDiamond => poly(&[(0.0, -0.707), (0.424, 0.0), (0.0, 0.707), (-0.424, 0.0)]),
        Marker::Pentagon => poly(&[
            (0.0, 0.5),
            (-0.476, 0.155),
            (-0.294, -0.405),
            (0.294, -0.405),
            (0.476, 0.155),
        ]),
        Marker::PlusFilled => poly(&[
            (-0.167, -0.5),
            (0.167, -0.5),
            (0.167, -0.167),
            (0.5, -0.167),
            (0.5, 0.167),
            (0.167, 0.167),
            (0.167, 0.5),
            (-0.167, 0.5),
            (-0.167, 0.167),
            (-0.5, 0.167),
            (-0.5, -0.167),
            (-0.167, -0.167),
        ]),
        Marker::Hexagon1 => poly(&[
            (0.0, 0.5),
            (-0.433, 0.25),
            (-0.433, -0.25),
            (0.0, -0.5),
            (0.433, -0.25),
            (0.433, 0.25),
        ]),
        Marker::Hexagon2 => poly(&[
            (-0.25, 0.433),
            (-0.5, 0.0),
            (-0.25, -0.433),
            (0.25, -0.433),
            (0.5, 0.0),
            (0.25, 0.433),
        ]),
        Marker::Octagon => poly(&[
            (-0.191, 0.462),
            (-0.462, 0.191),
            (-0.462, -0.191),
            (-0.191, -0.462),
            (0.191, -0.462),
            (0.462, -0.191),
            (0.462, 0.191),
            (0.191, 0.462),
        ]),
        Marker::Star => poly(&[
            (0.0, 0.5),
            (-0.112, 0.155),
            (-0.476, 0.155),
            (-0.182, -0.059),
            (-0.294, -0.405),
            (0.0, -0.191),
            (0.294, -0.405),
            (0.182, -0.059),
            (0.476, 0.155),
            (0.112, 0.155),
        ]),
        Marker::X => poly(&[
            (-0.25, -0.5),
            (0.0, -0.25),
            (0.25, -0.5),
            (0.5, -0.25),
            (0.25, 0.0),
            (0.5, 0.25),
            (0.25, 0.5),
            (0.0, 0.25),
            (-0.25, 0.5),
            (-0.5, 0.25),
            (-0.25, 0.0),
            (-0.5, -0.25),
        ]),
        Marker::TriangleUp => poly(&[(0.0, 0.5), (-0.5, -0.5), (0.5, -0.5)]),
        Marker::TriangleDown => poly(&[(0.0, -0.5), (0.5, 0.5), (-0.5, 0.5)]),
        Marker::TriangleLeft => poly(&[(-0.5, 0.0), (0.5, -0.5), (0.5, 0.5)]),
        Marker::TriangleRight => poly(&[(0.5, 0.0), (-0.5, 0.5), (-0.5, -0.5)]),
        Marker::Tick1 | Marker::Tick2 | Marker::Tick3 | Marker::Tick4 => {
            let (stem, arm_a, arm_b) = match marker {
                Marker::Tick1 => ((0.0, -0.5), (0.4, 0.25), (-0.4, 0.25)),
                Marker::Tick2 => ((0.0, 0.5), (-0.4, -0.25), (0.4, -0.25)),
                Marker::Tick3 => ((-0.5, 0.0), (0.25, -0.4), (0.25, 0.4)),
                _ => ((0.5, 0.0), (-0.25, 0.4), (-0.25, -0.4)),
            };
            MarkerShape::Strokes(vec![
                ((0.0, 0.0), stem),
                ((0.0, 0.0), arm_a),
                ((0.0, 0.0), arm_b),
            ])
        }
        Marker::Cross => {
            MarkerShape::Strokes(vec![((-0.5, -0.5), (0.5, 0.5)), ((-0.5, 0.5), (0.5, -0.5))])
        }
        Marker::Plus => {
            MarkerShape::Strokes(vec![((-0.5, 0.0), (0.5, 0.0)), ((0.0, -0.5), (0.0, 0.5))])
        }
        Marker::Vline => MarkerShape::Strokes(vec![((0.0, -0.5), (0.0, 0.5))]),
        Marker::Hline => MarkerShape::Strokes(vec![((-0.5, 0.0), (0.5, 0.0))]),
        Marker::Point => MarkerShape::Circle(0.5),
        Marker::None | Marker::Circle => MarkerShape::Circle(1.0),
    }
}

/// One scatter marker centred on canvas pixel `pos`, with pixel radius `r`.
/// `fill` paints the interior and `edge` the outline; a fully transparent
/// `fill` draws the outline only (Matplotlib's `markerfacecolor="none"`).
#[allow(clippy::too_many_arguments)]
pub(super) fn draw_marker<DB: DrawingBackend, C: Color>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    base: (i32, i32),
    pos: (i32, i32),
    r: f64,
    fill: C,
    edge: C,
    stroke: u32,
    marker: Marker,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let (x, y) = (pos.0 - base.0, pos.1 - base.1);
    let ri = r.round().max(1.0);
    let span = 2.0 * ri;
    let hollow = fill.to_rgba().3 == 0.0;
    let map = |(vx, vy): (f64, f64)| {
        (
            (x as f64 + vx * span).round() as i32,
            (y as f64 - vy * span).round() as i32,
        )
    };
    match marker_shape(marker) {
        MarkerShape::Polygon(verts) => {
            if marker == Marker::Square {
                let corners = [
                    (x - ri as i32, y - ri as i32),
                    (x + ri as i32, y + ri as i32),
                ];
                if hollow {
                    // Keep a square marker as an SVG `<rect>`; the raster backends
                    // produce the same pixels either way.
                    area.draw(&Rectangle::new(corners, edge.stroke_width(stroke.max(1))))?;
                } else {
                    area.draw(&Rectangle::new(corners, fill.filled()))?;
                }
            } else {
                let pts: Vec<(i32, i32)> = verts.iter().map(|v| map(*v)).collect();
                if hollow {
                    area.draw(&Polygon::new(pts, edge.stroke_width(stroke.max(1))))?;
                } else {
                    area.draw(&Polygon::new(pts, fill.filled()))?;
                }
            }
        }
        MarkerShape::Strokes(segs) => {
            for (a, b) in segs {
                area.draw(&PathElement::new(
                    vec![map(a), map(b)],
                    edge.stroke_width(stroke),
                ))?;
            }
        }
        MarkerShape::Circle(frac) => {
            // Matplotlib strokes markers with their edge width even when the
            // edge colour is the face, so the visible radius includes half of
            // it (scatter's default linewidths is 1 pt).
            let radius = (ri * frac + stroke as f64 / 2.0).round().max(1.0) as u32;
            if hollow {
                area.draw(&Circle::new(
                    (x, y),
                    radius,
                    edge.stroke_width(stroke.max(1)),
                ))?;
            } else {
                area.draw(&Circle::new((x, y), radius, fill.filled()))?;
            }
        }
    }
    Ok(())
}

/// Paint one marker into a transparent raster layer. Dense raster scatters use
/// this instead of one SVG element per point, which keeps resvg's per-element
/// work out of the save path.
#[allow(clippy::too_many_arguments)]
pub(super) fn draw_marker_raster(
    pixmap: &mut tiny_skia::Pixmap,
    base: (i32, i32),
    pos: (i32, i32),
    r: f64,
    fill: RGBAColor,
    edge: RGBAColor,
    stroke: u32,
    marker: Marker,
) {
    let (x, y) = ((pos.0 - base.0) as f64, (pos.1 - base.1) as f64);
    // Keep the fractional radius on the dense raster path: rounding it down
    // shrank every small marker (s=4 is 1.39 px) to a hard two-pixel block
    // instead of an anti-aliased disc.
    let r = r.clamp(1.0, MAX_MARKER_RADIUS);
    let span = 2.0 * r;
    let hollow = fill.3 == 0.0;
    let map = |(vx, vy): (f64, f64)| ((x + vx * span) as f32, (y - vy * span) as f32);
    let paint_of = |col: RGBAColor| {
        let alpha = (col.3.clamp(0.0, 1.0) * 255.0).round() as u8;
        tiny_skia::Paint {
            shader: tiny_skia::Shader::SolidColor(tiny_skia::Color::from_rgba8(
                col.0, col.1, col.2, alpha,
            )),
            anti_alias: true,
            ..Default::default()
        }
    };
    let paint = paint_of(if hollow { edge } else { fill });
    match marker_shape(marker) {
        MarkerShape::Strokes(segs) => {
            let mut pb = tiny_skia::PathBuilder::new();
            for (a, b) in segs {
                let (ax, ay) = map(a);
                let (bx, by) = map(b);
                pb.move_to(ax, ay);
                pb.line_to(bx, by);
            }
            if let Some(path) = pb.finish() {
                let stroke = tiny_skia::Stroke {
                    width: stroke.max(1) as f32,
                    ..Default::default()
                };
                pixmap.stroke_path(
                    &path,
                    &paint_of(edge),
                    &stroke,
                    tiny_skia::Transform::identity(),
                    None,
                );
            }
        }
        MarkerShape::Circle(frac) => {
            let mut pb = tiny_skia::PathBuilder::new();
            pb.push_circle(x as f32, y as f32, (r * frac).max(1.0) as f32);
            if let Some(path) = pb.finish() {
                if hollow {
                    if stroke > 0 {
                        let outline = tiny_skia::Stroke {
                            width: stroke as f32,
                            ..Default::default()
                        };
                        pixmap.stroke_path(
                            &path,
                            &paint_of(edge),
                            &outline,
                            tiny_skia::Transform::identity(),
                            None,
                        );
                    }
                } else {
                    pixmap.fill_path(
                        &path,
                        &paint,
                        tiny_skia::FillRule::Winding,
                        tiny_skia::Transform::identity(),
                        None,
                    );
                    // A face-coloured edge like Matplotlib's marker linewidth.
                    if stroke > 0 {
                        let outline = tiny_skia::Stroke {
                            width: stroke as f32,
                            ..Default::default()
                        };
                        pixmap.stroke_path(
                            &path,
                            &paint,
                            &outline,
                            tiny_skia::Transform::identity(),
                            None,
                        );
                    }
                }
            }
        }
        MarkerShape::Polygon(verts) => {
            let mut pb = tiny_skia::PathBuilder::new();
            if let Some((vx, vy)) = verts.first() {
                let (px, py) = map((*vx, *vy));
                pb.move_to(px, py);
                for v in &verts[1..] {
                    let (px, py) = map(*v);
                    pb.line_to(px, py);
                }
                pb.close();
            }
            if let Some(path) = pb.finish() {
                pixmap.fill_path(
                    &path,
                    &paint,
                    tiny_skia::FillRule::Winding,
                    tiny_skia::Transform::identity(),
                    None,
                );
            }
        }
    }
}
