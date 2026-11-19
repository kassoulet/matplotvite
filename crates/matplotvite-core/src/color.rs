use plotters::prelude::RGBAColor;

use crate::cmap_data::lookup;

/// A parsed colour. Unknown names use the historical matplotlib-blue fallback.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Color(pub RGBAColor);

impl Color {
    pub fn parse(value: &str) -> Self {
        Self(color(value))
    }

    pub fn rgba(self) -> RGBAColor {
        self.0
    }
}

impl Default for Color {
    fn default() -> Self {
        Self(RGBAColor(31, 119, 180, 1.0))
    }
}

/// Parse a normalised colour (`#rgb`, `#rrggbb`, `#rrggbbaa`) or a legacy name.
/// "none"/"transparent" become fully transparent so callers can draw them
/// without special-casing.
pub fn color(s: &str) -> RGBAColor {
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

/// A parsed colormap name, including its optional `_r` reversal.
///
/// Unknown names fall back to viridis, matching the renderer's previous
/// behaviour for custom Python colormaps the Rust registry does not contain.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Cmap {
    name: &'static str,
    reversed: bool,
}

impl Cmap {
    pub fn parse(value: &str) -> Self {
        let text = value.trim();
        let (base, reversed) = match text.strip_suffix("_r") {
            Some(base) => (base, true),
            None => (text, false),
        };
        let name = lookup(base)
            .or_else(|| lookup("viridis"))
            .map(|def| def.name)
            .unwrap_or("");
        Self { name, reversed }
    }

    /// One matplotlib colormap lookup, clamped to the sampled LUT.
    pub fn sample(self, t: f64) -> [u8; 4] {
        // If the registry itself is empty, return opaque black rather than
        // panicking on user input.
        let Some(def) = lookup(self.name) else {
            return [0, 0, 0, 255];
        };
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
        if self.reversed {
            index = n - 1 - index;
        }
        let color = def.colors[index];
        [color[0], color[1], color[2], 255]
    }
}
