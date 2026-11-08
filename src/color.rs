use plotters::prelude::RGBAColor;

use crate::cmap_data::lookup;

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

/// One matplotlib colormap lookup; `_r` names reverse the sampled LUT.
/// Unknown names fall back to viridis, matching the previous behaviour.
pub(crate) fn colormap(name: &str, t: f64) -> [u8; 4] {
    let (base, reversed) = match name.strip_suffix("_r") {
        Some(base) => (base, true),
        None => (name, false),
    };
    let def = lookup(base)
        .or_else(|| lookup("viridis"))
        .expect("viridis is part of the registry");
    let n = def.colors.len();
    if n == 0 {
        return [0, 0, 0, 255];
    }
    let t = if t.is_finite() {
        t.clamp(0.0, 1.0)
    } else {
        0.0
    };
    let mut index = (t * n as f64) as usize;
    if index >= n {
        index = n - 1;
    }
    if reversed {
        index = n - 1 - index;
    }
    let color = def.colors[index];
    [color[0], color[1], color[2], 255]
}
