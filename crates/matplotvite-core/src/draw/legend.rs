//! Legend obstacle collection and placement.

use super::markers::draw_marker;
use super::*;

use crate::model::Legend;

/// Candidate axes-fraction placements for `loc="best"`, in matplotlib's
/// preference order (`AnchoredOffsetbox.codes`). Ties keep the earlier entry.
const BEST_LOCS: [&str; 10] = [
    "upper right",
    "upper left",
    "lower left",
    "lower right",
    "right",
    "center left",
    "center right",
    "lower center",
    "upper center",
    "center",
];

/// Per-artist vertex cap for the `"best"` scorer: the score only needs a
/// representative sample, and dense series should not be copied per candidate.
const LEGEND_SCORE_VERTICES: usize = 1024;

/// Pixel-space geometry of the drawn artists, mirroring matplotlib's
/// `Legend._auto_legend_data`: line paths, collection offsets and patch boxes.
#[derive(Default)]
struct LegendObstacles {
    lines: Vec<Vec<(f64, f64)>>,
    offsets: Vec<(f64, f64)>,
    boxes: Vec<(f64, f64, f64, f64)>,
}

impl LegendObstacles {
    fn push_line(&mut self, mut pts: Vec<(f64, f64)>) {
        // Bound the work for artists that emit thousands of small paths.
        if pts.len() < 2 || self.lines.len() >= 4096 {
            return;
        }
        if pts.len() > LEGEND_SCORE_VERTICES {
            let stride = pts.len().div_ceil(LEGEND_SCORE_VERTICES);
            let last = *pts.last().expect("non-empty polyline");
            let mut thinned = Vec::with_capacity(LEGEND_SCORE_VERTICES + 1);
            thinned.extend(pts.iter().step_by(stride).copied());
            thinned.push(last);
            pts = thinned;
        }
        self.lines.push(pts);
    }

    fn push_point(&mut self, (x, y): (f64, f64)) {
        if x.is_finite() && y.is_finite() && self.offsets.len() < 8192 {
            self.offsets.push((x, y));
        }
    }

    /// matplotlib's badness: containment counts for line vertices and point
    /// offsets, box overlaps for filled patches, plus one per line that touches
    /// the candidate box.
    fn badness(&self, x: f64, y: f64, w: f64, h: f64) -> usize {
        let (x0, y0, x1, y1) = (x, y, x + w, y + h);
        let inside = |p: (f64, f64)| p.0 >= x0 && p.0 <= x1 && p.1 >= y0 && p.1 <= y1;
        let mut badness = self.offsets.iter().filter(|p| inside(**p)).count();
        for line in &self.lines {
            badness += line.iter().filter(|p| inside(**p)).count();
            if line.iter().any(|p| inside(*p)) || polyline_crosses_box(line, x0, y0, x1, y1) {
                badness += 1;
            }
        }
        badness
            + self
                .boxes
                .iter()
                .filter(|b| box_overlaps(b, x0, y0, x1, y1))
                .count()
    }
}

fn segments_cross(a: (f64, f64), b: (f64, f64), c: (f64, f64), d: (f64, f64)) -> bool {
    let cross = |p: (f64, f64), q: (f64, f64), r: (f64, f64)| {
        (q.0 - p.0) * (r.1 - p.1) - (q.1 - p.1) * (r.0 - p.0)
    };
    let (d1, d2) = (cross(c, d, a), cross(c, d, b));
    let (d3, d4) = (cross(a, b, c), cross(a, b, d));
    ((d1 > 0.0) != (d2 > 0.0)) && ((d3 > 0.0) != (d4 > 0.0))
}

fn polyline_crosses_box(line: &[(f64, f64)], x0: f64, y0: f64, x1: f64, y1: f64) -> bool {
    let corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)];
    line.windows(2)
        .any(|seg| (0..4).any(|i| segments_cross(seg[0], seg[1], corners[i], corners[(i + 1) % 4])))
}

fn box_overlaps(b: &(f64, f64, f64, f64), x0: f64, y0: f64, x1: f64, y1: f64) -> bool {
    b.0 < x1 && x0 < b.2 && b.1 < y1 && y0 < b.3
}

fn legend_anchor(loc: &str) -> (f64, f64) {
    match loc {
        "upper left" => (0.0, 1.0),
        "lower left" => (0.0, 0.0),
        "lower right" => (1.0, 0.0),
        "center" => (0.5, 0.5),
        "center left" => (0.0, 0.5),
        "center right" | "right" => (1.0, 0.5),
        "upper center" => (0.5, 1.0),
        "lower center" => (0.5, 0.0),
        _ => (1.0, 1.0),
    }
}

fn anchored_legend_pos(
    ax: f64,
    ay: f64,
    loc: &str,
    box_w: f64,
    box_h: f64,
    rect: (i32, i32, i32, i32),
) -> (f64, f64) {
    let (left, top, right, bottom) = rect;
    let px = left as f64 + ax * (right - left) as f64;
    let py = bottom as f64 - ay * (bottom - top) as f64;
    let x = if loc.contains("right") {
        px - box_w
    } else if loc.contains("left") {
        px
    } else {
        px - box_w / 2.0
    };
    let y = if loc.contains("upper") {
        py
    } else if loc.contains("lower") {
        py - box_h
    } else {
        py - box_h / 2.0
    };
    (
        x.clamp(left as f64, (right as f64 - box_w).max(left as f64)),
        y.clamp(top as f64, (bottom as f64 - box_h).max(top as f64)),
    )
}

/// Score every candidate placement and keep the least-overlapping one, stopping
/// at the first zero-badness candidate like matplotlib.
fn best_legend_pos(
    obstacles: &LegendObstacles,
    box_w: f64,
    box_h: f64,
    rect: (i32, i32, i32, i32),
) -> (f64, f64) {
    let mut best = anchored_legend_pos(1.0, 1.0, "upper right", box_w, box_h, rect);
    let mut best_badness = usize::MAX;
    for loc in BEST_LOCS {
        let (ax, ay) = legend_anchor(loc);
        let pos = anchored_legend_pos(ax, ay, loc, box_w, box_h, rect);
        let badness = obstacles.badness(pos.0, pos.1, box_w, box_h);
        if badness < best_badness {
            best_badness = badness;
            best = pos;
        }
        if badness == 0 {
            break;
        }
    }
    best
}

pub(super) fn legend_corner_radius(font_size: f64) -> f64 {
    // Matplotlib's rounded legend box scales with the text, not the canvas.
    (font_size * 0.5).clamp(3.0, 12.0)
}

pub(super) fn draw_rounded_frame<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    rect: (f64, f64, f64, f64),
    fill: RGBAColor,
    border: RGBAColor,
    radius: f64,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let (x, y, w, h) = rect;
    let r = radius.min(w / 2.0).min(h / 2.0);
    let mut pts = Vec::with_capacity(20);
    let corners = [
        (
            x + r,
            y + r,
            std::f64::consts::PI,
            1.5 * std::f64::consts::PI,
        ),
        (
            x + w - r,
            y + r,
            1.5 * std::f64::consts::PI,
            2.0 * std::f64::consts::PI,
        ),
        (x + w - r, y + h - r, 0.0, 0.5 * std::f64::consts::PI),
        (
            x + r,
            y + h - r,
            0.5 * std::f64::consts::PI,
            std::f64::consts::PI,
        ),
    ];
    for (cx, cy, start, end) in corners {
        for i in 0..=4 {
            let angle = start + (end - start) * i as f64 / 4.0;
            pts.push(((cx + r * angle.cos()) as i32, (cy + r * angle.sin()) as i32));
        }
    }
    area.draw(&Polygon::new(pts.clone(), fill.filled()))?;
    let mut outline = pts;
    if let Some(first) = outline.first().copied() {
        outline.push(first);
    }
    area.draw(&PathElement::new(outline, border.stroke_width(1)))?;
    Ok(())
}

/// Draw the legend myself so placement, columns, title and frame options all
/// work; plotters' built-in legend only supports a single column.
fn draw_legend<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    rect: (i32, i32, i32, i32),
    entries: &[LegendEntry],
    opts: &Legend,
    obstacles: &LegendObstacles,
    text: RGBAColor,
    dpi: f64,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    if entries.is_empty() {
        return Ok(());
    }
    let fs = text_px(opts.fontsize.max(6.0), dpi);
    let title_fs = text_px(opts.title_fontsize.max(6.0), dpi);
    let cols = opts.ncol.max(1);
    let rows = entries.len().div_ceil(cols);
    let col_w = entries
        .iter()
        .map(|e| crate::fonts::text_width(&e.label, fs))
        .fold(0.0, f64::max)
        + 36.0;
    let row_h = fs * 1.6;
    let title_h = if opts.title.is_empty() {
        0.0
    } else {
        title_fs * 1.5
    };
    let box_w = col_w * cols as f64 + 8.0;
    let box_h = rows as f64 * row_h + title_h + 8.0;
    let loc = opts.loc.as_str();
    let (x, y) = if let Some((ax, ay)) = opts.anchor {
        anchored_legend_pos(ax, ay, loc, box_w, box_h, rect)
    } else if loc == "best" {
        best_legend_pos(obstacles, box_w, box_h, rect)
    } else {
        let (ax, ay) = legend_anchor(loc);
        anchored_legend_pos(ax, ay, loc, box_w, box_h, rect)
    };
    if opts.frameon {
        draw_rounded_frame(
            area,
            (x, y, box_w, box_h),
            RGBAColor(255, 255, 255, 0.8),
            RGBAColor(204, 204, 204, 1.0),
            legend_corner_radius(fs),
        )?;
    }
    if !opts.title.is_empty() {
        let style = (opts.family.as_str(), title_fs.round() as u32)
            .into_font()
            .color(&text);
        area.draw(&Text::new(
            opts.title.clone(),
            ((x + box_w / 2.0) as i32, (y + title_h / 2.0) as i32),
            style.pos(Pos::new(HPos::Center, VPos::Center)),
        ))?;
    }
    for (i, entry) in entries.iter().enumerate() {
        let col = i / rows.max(1);
        let row = i % rows.max(1);
        let cx = x + 6.0 + col as f64 * col_w;
        let cy = y + title_h + 4.0 + row as f64 * row_h + row_h / 2.0;
        match &entry.swatch {
            LegendSwatch::Line(c, w) => area.draw(&PathElement::new(
                vec![(cx as i32, cy as i32), ((cx + 20.0) as i32, cy as i32)],
                c.stroke_width(*w),
            ))?,
            LegendSwatch::LineMarker(c, w, marker) => {
                area.draw(&PathElement::new(
                    vec![(cx as i32, cy as i32), ((cx + 20.0) as i32, cy as i32)],
                    c.stroke_width(*w),
                ))?;
                draw_marker(
                    area,
                    (0, 0),
                    ((cx + 10.0) as i32, cy as i32),
                    4.0,
                    *c,
                    *c,
                    1,
                    *marker,
                )?;
            }
            LegendSwatch::Marker(c, marker) => draw_marker(
                area,
                (0, 0),
                ((cx + 10.0) as i32, cy as i32),
                4.0,
                *c,
                *c,
                1,
                *marker,
            )?,
            LegendSwatch::Rect(c) | LegendSwatch::Collection(c) => area.draw(&Rectangle::new(
                [
                    ((cx + 2.0) as i32, (cy - 5.0) as i32),
                    ((cx + 22.0) as i32, (cy + 5.0) as i32),
                ],
                c.filled(),
            ))?,
            LegendSwatch::Circle(c) => {
                area.draw(&Circle::new(((cx + 10.0) as i32, cy as i32), 5, c.filled()))?
            }
        }
        let style = (opts.family.as_str(), fs.round() as u32)
            .into_font()
            .color(&text);
        area.draw(&Text::new(
            entry.label.clone(),
            ((cx + 28.0) as i32, cy as i32),
            style.pos(Pos::new(HPos::Left, VPos::Center)),
        ))?;
    }
    Ok(())
}

/// Collect the pixel geometry of drawn artists, then place the custom or
/// plotters-managed legend. Keeping this together guarantees `loc="best"` sees
/// exactly the layers that were already drawn.
#[allow(clippy::too_many_arguments)]
pub(super) fn draw_legend_section<'a, DB, FX, FY>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    chart: &mut ChartContext<'a, DB, Cartesian2d<RangedCoordf64, RangedCoordf64>>,
    p: &Panel,
    entries: &mut Vec<LegendEntry>,
    tx: &FX,
    ty: &FY,
    x0: f64,
    x1: f64,
    y0: f64,
    y1: f64,
    fg: RGBAColor,
    dpi: f64,
    custom_legend: bool,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB: DrawingBackend + 'a,
    DB::ErrorType: 'static,
    FX: Fn(f64) -> f64,
    FY: Fn(f64) -> f64,
{
    // Matplotlib lists handles in artist creation order; artists the model did
    // not stamp keep their draw order after the stamped ones, lines first.
    entries.sort_by_key(|entry| {
        let kind = match &entry.swatch {
            LegendSwatch::Line(..) | LegendSwatch::LineMarker(..) | LegendSwatch::Marker(..) => 0,
            LegendSwatch::Rect(_) => 1,
            LegendSwatch::Collection(_) | LegendSwatch::Circle(_) => 2,
        };
        let seen = p.legend.order.iter().position(|l| *l == entry.label);
        (seen.unwrap_or(usize::MAX), kind)
    });
    if p.legend.labels.is_empty() {
        // Matplotlib hides artists whose label starts with an underscore from
        // automatic legends (`_nolegend_` is the common sentinel).
        entries.retain(|entry| !entry.label.starts_with('_'));
    } else {
        for (entry, label) in entries.iter_mut().zip(&p.legend.labels) {
            entry.label = label.clone();
        }
    }
    let legend_obstacles = if custom_legend && p.legend.loc == "best" {
        let pa = chart.plotting_area();
        let base = area.get_base_pixel();
        let mut obstacles = LegendObstacles::default();
        let to_px = |x: f64, y: f64| {
            let (px, py) = pa.map_coordinate(&(tx(x), ty(y)));
            (px as f64 - base.0 as f64, py as f64 - base.1 as f64)
        };
        let sample = |xs: &OwnedArray1, ys: &OwnedArray1| -> Vec<(f64, f64)> {
            let (xs, ys) = (xs.as_array(), ys.as_array());
            let n = xs.len().min(ys.len());
            let stride = n.div_ceil(LEGEND_SCORE_VERTICES).max(1);
            (0..n)
                .step_by(stride)
                .map(|i| to_px(xs[i], ys[i]))
                .collect()
        };
        for s in &p.series {
            obstacles.push_line(sample(&s.x, &s.y));
        }
        for bar in &p.bars {
            let (left, bottom) = (bar.left.as_array(), bar.bottom.as_array());
            let (width, height) = (bar.width.as_array(), bar.height.as_array());
            for i in 0..left
                .len()
                .min(bottom.len())
                .min(width.len())
                .min(height.len())
            {
                let (ax0, ay0) = to_px(left[i], bottom[i]);
                let (ax1, ay1) = to_px(left[i] + width[i], bottom[i] + height[i]);
                obstacles
                    .boxes
                    .push((ax0.min(ax1), ay0.min(ay1), ax0.max(ax1), ay0.max(ay1)));
            }
        }
        for band in &p.bands {
            obstacles.push_line(sample(&band.x, &band.y));
        }
        for sc in &p.scatter {
            let (xs, ys) = (sc.x.as_array(), sc.y.as_array());
            let n = xs.len().min(ys.len());
            let stride = n.div_ceil(LEGEND_SCORE_VERTICES).max(1);
            for i in (0..n).step_by(stride) {
                obstacles.push_point(to_px(xs[i], ys[i]));
            }
        }
        for err in &p.errors {
            let (xs, ys) = (err.0.as_array(), err.1.as_array());
            let n = xs.len().min(ys.len());
            let stride = n.div_ceil(LEGEND_SCORE_VERTICES).max(1);
            for i in (0..n).step_by(stride) {
                obstacles.push_point(to_px(xs[i], ys[i]));
            }
        }
        for patch in &p.patches {
            match patch.kind.as_str() {
                "rect" => {
                    let (ax0, ay0) = to_px(patch.x, patch.y);
                    let (ax1, ay1) = to_px(patch.x + patch.width, patch.y + patch.height);
                    obstacles
                        .boxes
                        .push((ax0.min(ax1), ay0.min(ay1), ax0.max(ax1), ay0.max(ay1)));
                }
                "circle" => {
                    let (cx, cy) = to_px(patch.x, patch.y);
                    let (rx, _) = to_px(patch.x + patch.width, patch.y);
                    let (_, ry) = to_px(patch.x, patch.y + patch.width);
                    let (rx, ry) = ((rx - cx).abs(), (ry - cy).abs());
                    let ring = (0..16)
                        .map(|i| {
                            let t = i as f64 / 16.0 * std::f64::consts::TAU;
                            (cx + rx * t.cos(), cy + ry * t.sin())
                        })
                        .collect();
                    obstacles.push_line(ring);
                }
                _ => {
                    let pts = patch
                        .points
                        .as_chunks::<2>()
                        .0
                        .iter()
                        .map(|pair| to_px(pair[0], pair[1]))
                        .collect();
                    obstacles.push_line(pts);
                }
            }
        }
        for coll in &p.collections {
            let n = coll.points.len() / 2;
            let stride = n.div_ceil(LEGEND_SCORE_VERTICES).max(1);
            for i in (0..n).step_by(stride) {
                obstacles.push_point(to_px(coll.points[i * 2], coll.points[i * 2 + 1]));
            }
            for seg in &coll.segments {
                let pts = seg
                    .as_chunks::<2>()
                    .0
                    .iter()
                    .map(|pair| to_px(pair[0], pair[1]))
                    .collect();
                obstacles.push_line(pts);
            }
        }
        obstacles
    } else {
        LegendObstacles::default()
    };
    if p.legend.show && custom_legend {
        let base = area.get_base_pixel();
        let pa = chart.plotting_area();
        let tl = pa.map_coordinate(&(x0, y1));
        let br = pa.map_coordinate(&(x1, y0));
        draw_legend(
            area,
            (tl.0 - base.0, tl.1 - base.1, br.0 - base.0, br.1 - base.1),
            entries,
            &p.legend,
            &legend_obstacles,
            fg,
            dpi,
        )?;
    } else if p.legend.show {
        let loc = p.legend.loc.as_str();
        let position = match loc {
            "upper left" => SeriesLabelPosition::UpperLeft,
            "upper center" => SeriesLabelPosition::UpperMiddle,
            "lower left" => SeriesLabelPosition::LowerLeft,
            "lower center" => SeriesLabelPosition::LowerMiddle,
            "lower right" => SeriesLabelPosition::LowerRight,
            "center left" => SeriesLabelPosition::MiddleLeft,
            "center right" | "right" => SeriesLabelPosition::MiddleRight,
            "center" => SeriesLabelPosition::MiddleRight,
            _ => SeriesLabelPosition::UpperRight,
        };
        // Registered here, after sorting, so plotters lists them in order.
        for entry in entries.iter() {
            let blank = || {
                std::iter::once(Rectangle::new(
                    [(0.0f64, 0.0f64), (0.0f64, 0.0f64)],
                    RGBColor(0, 0, 0).mix(0.0).filled(),
                ))
            };
            let label = entry.label.as_str();
            match entry.swatch.clone() {
                LegendSwatch::Line(c, w) | LegendSwatch::LineMarker(c, w, _) => {
                    chart
                        .draw_series(blank())?
                        .label(label)
                        .legend(move |(x, y)| {
                            PathElement::new(vec![(x, y), (x + 20, y)], c.stroke_width(w))
                        });
                }
                LegendSwatch::Marker(c, _) | LegendSwatch::Circle(c) => {
                    chart
                        .draw_series(blank())?
                        .label(label)
                        .legend(move |(x, y)| Circle::new((x + 10, y + 4), 4, c.filled()));
                }
                LegendSwatch::Rect(c) | LegendSwatch::Collection(c) => {
                    chart
                        .draw_series(blank())?
                        .label(label)
                        .legend(move |(x, y)| {
                            Rectangle::new([(x, y - 3), (x + 20, y + 7)], c.filled())
                        });
                }
            }
        }
        let mut labels = chart.configure_series_labels();
        labels.position(position).label_font((
            p.legend.family.as_str(),
            text_px(p.legend.fontsize.max(6.0), dpi).round() as u32,
        ));
        if p.legend.frameon {
            labels
                .background_style(RGBAColor(255, 255, 255, 0.92))
                .border_style(RGBColor(200, 200, 200))
                .margin(12)
                .legend_area_size(24);
        } else {
            labels
                .background_style(TRANSPARENT)
                .border_style(TRANSPARENT);
        }
        labels.draw()?;
    }
    Ok(())
}
