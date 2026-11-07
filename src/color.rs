use plotters::prelude::RGBAColor;

/// Parse a normalised colour (`#rgb`, `#rrggbb`, `#rrggbbaa`) or a legacy name.
/// "none"/"transparent" become fully transparent so callers can draw them
/// without special-casing.
pub(crate) fn color(s: &str) -> RGBAColor {
    let raw = s.trim();
    let lower = raw.to_ascii_lowercase();
    if lower == "none" || lower == "transparent" {
        return RGBAColor(0, 0, 0, 0.0);
    }
    let named = match lower.as_str() {
        "red" | "r" => Some("ff0000"),
        "green" | "g" => Some("008000"),
        "blue" | "b" => Some("0000ff"),
        "orange" => Some("ffa500"),
        "black" | "k" => Some("000000"),
        "white" | "w" => Some("ffffff"),
        "cyan" | "c" => Some("00ffff"),
        "magenta" | "m" => Some("ff00ff"),
        "yellow" | "y" => Some("ffff00"),
        "grey" | "gray" => Some("808080"),
        _ => None,
    };
    let h = named
        .unwrap_or(raw)
        .trim_start_matches('#')
        .to_ascii_lowercase();
    let valid = h.chars().all(|c| c.is_ascii_hexdigit());
    let expand = |ch: char| {
        let v = ch.to_digit(16).unwrap_or(1) as u8;
        v * 16 + v
    };
    let byte = |i: usize| u8::from_str_radix(&h[i..i + 2], 16).unwrap_or(0);
    if !valid {
        return RGBAColor(31, 119, 180, 1.0);
    }
    match h.len() {
        3 => {
            let chars: Vec<char> = h.chars().collect();
            RGBAColor(expand(chars[0]), expand(chars[1]), expand(chars[2]), 1.0)
        }
        6 => RGBAColor(byte(0), byte(2), byte(4), 1.0),
        8 => RGBAColor(byte(0), byte(2), byte(4), byte(6) as f64 / 255.0),
        _ => RGBAColor(31, 119, 180, 1.0),
    }
}

/// Minimal colormaps; unknown names fall back to viridis.
pub(crate) fn colormap(name: &str, t: f64) -> [u8; 4] {
    let t = if t.is_finite() {
        t.clamp(0.0, 1.0)
    } else {
        0.0
    };
    if name.eq_ignore_ascii_case("gray") || name.eq_ignore_ascii_case("grey") {
        let v = (t * 255.0).round() as u8;
        return [v, v, v, 255];
    }
    const VIRIDIS: [[u8; 3]; 9] = [
        [68, 1, 84],
        [72, 40, 120],
        [62, 74, 137],
        [49, 104, 142],
        [38, 130, 142],
        [31, 158, 137],
        [53, 183, 121],
        [109, 205, 89],
        [253, 231, 37],
    ];
    let pos = t * (VIRIDIS.len() - 1) as f64;
    let i = (pos.floor() as usize).min(VIRIDIS.len() - 2);
    let f = pos - i as f64;
    let (a, b) = (VIRIDIS[i], VIRIDIS[i + 1]);
    let mix = |k: usize| (a[k] as f64 + (b[k] as f64 - a[k] as f64) * f).round() as u8;
    [mix(0), mix(1), mix(2), 255]
}
