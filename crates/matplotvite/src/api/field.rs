//! Image, contour, quiver, patch and collection artists.

use super::*;

impl Axes<'_> {
    /// Display a 2-D scalar array as an image with an equal aspect ratio.
    pub fn imshow(&mut self, values: ArrayView2<'_, f64>) -> Result<&mut Self, ApiError> {
        let (rows, cols) = (values.shape()[0], values.shape()[1]);
        if rows == 0 || cols == 0 {
            return Err(ApiError::InvalidArgument(
                "imshow needs a non-empty 2-D array".into(),
            ));
        }
        self.panel.images.push((
            OwnedArrayD::from_array(
                Array2::from_shape_vec((rows, cols), values.iter().copied().collect())
                    .map_err(|e| ApiError::InvalidArgument(e.to_string()))?
                    .into_dyn(),
            ),
            Cmap::parse("viridis"),
            None,
            None,
            (-0.5, cols as f64 - 0.5, rows as f64 - 0.5, -0.5),
            true,
            1.0,
            "nearest".to_string(),
        ));
        self.panel.aspect = Some(1.0);
        self.panel.x.lim = Some((-0.5, cols as f64 - 0.5));
        self.panel.y.lim = Some((rows as f64 - 0.5, -0.5));
        self.last = None;
        Ok(self)
    }

    /// Draw arrows whose tails are `(x, y)` and whose components are `(u, v)`.
    pub fn quiver(
        &mut self,
        x: &[f64],
        y: &[f64],
        u: &[f64],
        v: &[f64],
    ) -> Result<&mut Self, ApiError> {
        check_xy(x, y)?;
        check_xy(x, u)?;
        check_xy(x, v)?;
        let color = self.next_color();
        self.panel.arrows.push(Arrow {
            x: OwnedArray1::from(x.to_vec()),
            y: OwnedArray1::from(y.to_vec()),
            u: OwnedArray1::from(u.to_vec()),
            v: OwnedArray1::from(v.to_vec()),
            colors: vec![color],
            scale: None,
            units: QuiverUnits::Width,
            scale_units: None,
            angles: "uv".to_string(),
            width: None,
            headwidth: 3.0,
            headlength: 5.0,
            headaxislength: 4.5,
            pivot: "tail".to_string(),
        });
        self.last = None;
        Ok(self)
    }

    /// Draw contour lines through a 2-D value grid.
    pub fn contour(
        &mut self,
        x: &[f64],
        y: &[f64],
        z: ArrayView2<'_, f64>,
        levels: &[f64],
    ) -> Result<&mut Self, ApiError> {
        self.push_contour(x, y, z, levels, false)
    }

    /// Draw filled contours through a 2-D value grid.
    pub fn contourf(
        &mut self,
        x: &[f64],
        y: &[f64],
        z: ArrayView2<'_, f64>,
        levels: &[f64],
    ) -> Result<&mut Self, ApiError> {
        self.push_contour(x, y, z, levels, true)
    }

    fn push_contour(
        &mut self,
        x: &[f64],
        y: &[f64],
        z: ArrayView2<'_, f64>,
        levels: &[f64],
        filled: bool,
    ) -> Result<&mut Self, ApiError> {
        let (rows, cols) = (z.shape()[0], z.shape()[1]);
        if rows == 0 || cols == 0 {
            return Err(ApiError::InvalidArgument(
                "contour needs a non-empty 2-D array".into(),
            ));
        }
        if x.len() != cols || y.len() != rows {
            return Err(ApiError::InvalidArgument(format!(
                "contour grid is {cols}x{rows}, got {} x values and {} y values",
                x.len(),
                y.len()
            )));
        }
        let provided = levels.to_vec();
        let levels = if provided.is_empty() {
            let mut lo = f64::INFINITY;
            let mut hi = f64::NEG_INFINITY;
            for value in z.iter().copied().filter(|value| value.is_finite()) {
                lo = lo.min(value);
                hi = hi.max(value);
            }
            if lo >= hi {
                lo -= 0.5;
                hi += 0.5;
            }
            (0..7)
                .map(|index| lo + (hi - lo) * index as f64 / 6.0)
                .collect()
        } else {
            provided
        };
        self.panel.contours.push((
            OwnedArray1::from(x.to_vec()),
            OwnedArray1::from(y.to_vec()),
            OwnedArray2::from_array(
                Array2::from_shape_vec((rows, cols), z.iter().copied().collect())
                    .map_err(|e| ApiError::InvalidArgument(e.to_string()))?,
            ),
            levels.clone(),
            vec![1.5; levels.len()],
            Vec::new(),
            Cmap::parse("viridis"),
            filled,
            1.0,
        ));
        self.last = None;
        Ok(self)
    }

    /// Add a vertical gradient strip for `cmap` over `vmin..vmax`.
    pub fn colorbar(&mut self, cmap: &str, vmin: f64, vmax: f64) -> &mut Self {
        let vmax = if vmax > vmin { vmax } else { vmin + 1.0 };
        self.panel.colorbar = Some((
            Cmap::parse(cmap),
            vmin,
            vmax,
            String::new(),
            false,
            None,
            10.0,
            "vertical".to_string(),
            "neither".to_string(),
            false,
            0.05,
        ));
        self
    }

    /// Add a data-space rectangle.
    pub fn rectangle(&mut self, x: f64, y: f64, width: f64, height: f64) -> &mut Self {
        self.push_patch("rect", x, y, width, height, Vec::new())
    }

    /// Add a data-space circle.
    pub fn circle(&mut self, x: f64, y: f64, radius: f64) -> &mut Self {
        self.push_patch("circle", x, y, radius, 0.0, Vec::new())
    }

    /// Add a closed polygon; `points` are data-space `(x, y)` vertices.
    pub fn polygon(&mut self, points: &[(f64, f64)]) -> &mut Self {
        let mut flat = Vec::with_capacity(points.len() * 2);
        for &(x, y) in points {
            flat.push(x);
            flat.push(y);
        }
        self.push_patch("polygon", 0.0, 0.0, 0.0, 0.0, flat)
    }

    fn push_patch(
        &mut self,
        kind: &str,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        points: Vec<f64>,
    ) -> &mut Self {
        let color = self.next_color();
        self.panel.patches.push(ArtistPatch {
            kind: kind.to_string(),
            x,
            y,
            width,
            height,
            points,
            facecolor: Some(color),
            edgecolor: None,
            linewidth: 1.0,
            alpha: 1.0,
            gid: String::new(),
            label: String::new(),
        });
        self.last = Some(LastArtist::Patch(self.panel.patches.len() - 1));
        self.sequence
            .push(LastArtist::Patch(self.panel.patches.len() - 1));
        self
    }

    /// Add a collection of unconnected polylines, each given as flat `x, y`
    /// pairs.
    pub fn line_collection(&mut self, segments: &[Vec<f64>]) -> &mut Self {
        let color = self.next_color();
        self.panel.collections.push(ArtistCollection {
            points: Vec::new(),
            segments: segments.to_vec(),
            sizes: Vec::new(),
            colors: vec![color],
            marker: Marker::None,
            alpha: 1.0,
            linewidth: 1.5,
            label: String::new(),
        });
        self.last = Some(LastArtist::Collection(self.panel.collections.len() - 1));
        self.sequence
            .push(LastArtist::Collection(self.panel.collections.len() - 1));
        self
    }

    /// Display a 2-D scalar array with an explicit colormap and value range.
    pub fn imshow_cmap(
        &mut self,
        values: ArrayView2<'_, f64>,
        cmap: &str,
        vmin: Option<f64>,
        vmax: Option<f64>,
    ) -> Result<&mut Self, ApiError> {
        let (rows, cols) = (values.shape()[0], values.shape()[1]);
        if rows == 0 || cols == 0 {
            return Err(ApiError::InvalidArgument(
                "imshow needs a non-empty 2-D array".into(),
            ));
        }
        self.panel.images.push((
            OwnedArrayD::from_array(
                Array2::from_shape_vec((rows, cols), values.iter().copied().collect())
                    .map_err(|e| ApiError::InvalidArgument(e.to_string()))?
                    .into_dyn(),
            ),
            Cmap::parse(cmap),
            vmin,
            vmax,
            (-0.5, cols as f64 - 0.5, rows as f64 - 0.5, -0.5),
            true,
            1.0,
            "nearest".to_string(),
        ));
        self.panel.aspect = Some(1.0);
        self.panel.x.lim = Some((-0.5, cols as f64 - 0.5));
        self.panel.y.lim = Some((rows as f64 - 0.5, -0.5));
        self.last = None;
        Ok(self)
    }
}
