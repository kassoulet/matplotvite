//! Native Rust figure builder.
//!
//! The builder constructs the same panel records as the Python facade and
//! renders them through `matplotvite-core`, so both front ends share one
//! drawing and encoding pipeline.

mod api;

pub use api::*;
