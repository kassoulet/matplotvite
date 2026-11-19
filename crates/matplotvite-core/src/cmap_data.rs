//! Colormap registry parsed once from `cmaps.txt` (see tools/generate_colormaps.py).

use std::sync::OnceLock;

pub struct CmapDef {
    pub name: &'static str,
    pub colors: Vec<[u8; 3]>,
}

pub fn cmaps() -> &'static [CmapDef] {
    static CMAPS: OnceLock<Vec<CmapDef>> = OnceLock::new();
    CMAPS.get_or_init(|| {
        include_str!("cmaps.txt")
            .lines()
            .filter(|l| !l.starts_with('#'))
            .filter_map(|l| {
                let mut it = l.split(' ');
                let name = it.next()?;
                let colors = it
                    .map(|h| {
                        let v = u32::from_str_radix(h, 16).unwrap_or(0);
                        [(v >> 16) as u8, (v >> 8) as u8, v as u8]
                    })
                    .collect();
                Some(CmapDef { name, colors })
            })
            .collect()
    })
}

/// Exact registry lookup first, then a case-insensitive fallback.
pub fn lookup(name: &str) -> Option<&'static CmapDef> {
    let all = cmaps();
    all.iter()
        .find(|c| c.name == name)
        .or_else(|| all.iter().find(|c| c.name.eq_ignore_ascii_case(name)))
}
