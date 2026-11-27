//! Ticks, limits, scales, grid, legend and label styling.

use super::*;

impl Axes<'_> {
    /// Set explicit x tick positions, keeping the automatic labels.
    pub fn xticks(&mut self, ticks: &[f64]) -> &mut Self {
        self.panel.ticks.xticks = Some(ticks.to_vec());
        self
    }

    /// Set explicit x tick positions and labels.
    pub fn xticks_with_labels(
        &mut self,
        ticks: &[f64],
        labels: &[&str],
    ) -> Result<&mut Self, ApiError> {
        check_labels(ticks, labels)?;
        self.panel.ticks.xticks = Some(ticks.to_vec());
        self.panel.ticks.xticklabels = Some(labels.iter().map(|value| value.to_string()).collect());
        Ok(self)
    }

    /// Set explicit y tick positions, keeping the automatic labels.
    pub fn yticks(&mut self, ticks: &[f64]) -> &mut Self {
        self.panel.ticks.yticks = Some(ticks.to_vec());
        self
    }

    /// Set explicit y tick positions and labels.
    pub fn yticks_with_labels(
        &mut self,
        ticks: &[f64],
        labels: &[&str],
    ) -> Result<&mut Self, ApiError> {
        check_labels(ticks, labels)?;
        self.panel.ticks.yticks = Some(ticks.to_vec());
        self.panel.ticks.yticklabels = Some(labels.iter().map(|value| value.to_string()).collect());
        Ok(self)
    }

    /// Apply tick styling to both axes.
    pub fn tick_params(&mut self, params: &TickParams) -> &mut Self {
        apply_tick_style(&mut self.panel.ticks.xstyle, params);
        apply_tick_style(&mut self.panel.ticks.ystyle, params);
        self
    }

    /// Apply tick styling to the x axis only.
    pub fn xtick_params(&mut self, params: &TickParams) -> &mut Self {
        apply_tick_style(&mut self.panel.ticks.xstyle, params);
        self
    }

    /// Apply tick styling to the y axis only.
    pub fn ytick_params(&mut self, params: &TickParams) -> &mut Self {
        apply_tick_style(&mut self.panel.ticks.ystyle, params);
        self
    }

    /// Set the x-axis scale.
    pub fn xscale(&mut self, scale: Scale) -> &mut Self {
        set_scale(self.panel, scale, true);
        self
    }

    /// Set the y-axis scale.
    pub fn yscale(&mut self, scale: Scale) -> &mut Self {
        set_scale(self.panel, scale, false);
        self
    }

    /// Hide the axes frame, ticks and tick labels while keeping the data.
    pub fn axis_off(&mut self) -> &mut Self {
        self.panel.axis_off = true;
        self
    }

    /// Set the data-unit aspect ratio (`1.0` is `"equal"`).
    pub fn aspect(&mut self, aspect: f64) -> Result<&mut Self, ApiError> {
        if aspect <= 0.0 || !aspect.is_finite() {
            return Err(ApiError::InvalidArgument(
                "aspect must be a positive finite number".into(),
            ));
        }
        self.panel.aspect = Some(aspect);
        Ok(self)
    }

    /// Widen the data limits to reach the aspect ratio instead of shrinking the
    /// plotting rectangle (`set_adjustable("datalim")`).
    pub fn aspect_datalim(&mut self, enabled: bool) -> &mut Self {
        self.panel.aspect_datalim = enabled;
        self
    }

    /// Apply grid styling and visibility.
    pub fn grid_options(&mut self, options: &GridOptions) -> &mut Self {
        let grid = Grid {
            show: options.show,
            color: options.color.as_deref().map(Color::parse),
            linewidth: options.linewidth,
            alpha: options.alpha,
            linestyle: options
                .linestyle
                .as_deref()
                .and_then(matplotvite_core::model::LineStyle::parse),
            axis: options.axis.clone(),
            minor_show: options.minor_show,
            minor_color: options.minor_color.as_deref().map(Color::parse),
            minor_linewidth: options.minor_linewidth,
            minor_alpha: options.minor_alpha,
        };
        self.panel.grid = grid;
        self
    }

    /// Apply legend placement and styling to the labelled artists.
    pub fn legend_options(&mut self, options: &LegendOptions) -> &mut Self {
        let fontsize = options.fontsize;
        self.panel.legend = Legend {
            show: true,
            loc: options.loc.clone(),
            family: self.panel.font_family.clone(),
            ncol: options.ncol,
            frameon: options.frameon,
            fontsize,
            title: options.title.clone(),
            title_fontsize: options.title_fontsize.unwrap_or(fontsize * 1.1),
            anchor: options.anchor,
            order: self.artist_labels(),
            ..Default::default()
        };
        self
    }

    /// Set the title font size, in points.
    pub fn title_size(&mut self, size: f64) -> &mut Self {
        self.panel.title_size = Some(size);
        self
    }

    /// Set the x-axis label font size, in points.
    pub fn xlabel_size(&mut self, size: f64) -> &mut Self {
        self.panel.x.label_size = Some(size);
        self
    }

    /// Set the y-axis label font size, in points.
    pub fn ylabel_size(&mut self, size: f64) -> &mut Self {
        self.panel.y.label_size = Some(size);
        self
    }

    /// Set the axes background colour.
    pub fn facecolor(&mut self, color: &str) -> &mut Self {
        self.panel.facecolor = Some(Color::parse(color));
        self
    }

    /// Set the colour used for titles, labels and ticks.
    pub fn foreground(&mut self, color: &str) -> &mut Self {
        self.panel.foreground = Some(Color::parse(color));
        self
    }

    /// Set explicit x- and y-axis label colours.
    pub fn label_colors(&mut self, x: &str, y: &str) -> &mut Self {
        self.panel.x.label_color = Some(Color::parse(x));
        self.panel.y.label_color = Some(Color::parse(y));
        self
    }

    /// Set the axes title.
    pub fn title(&mut self, title: impl Into<String>) -> &mut Self {
        self.panel.title = title.into();
        self
    }

    /// Set the x-axis label.
    pub fn xlabel(&mut self, label: impl Into<String>) -> &mut Self {
        self.panel.x.label = label.into();
        self
    }

    /// Set the y-axis label.
    pub fn ylabel(&mut self, label: impl Into<String>) -> &mut Self {
        self.panel.y.label = label.into();
        self
    }

    /// Set explicit x limits.
    pub fn xlim(&mut self, lo: f64, hi: f64) -> &mut Self {
        self.panel.x.lim = Some((lo, hi));
        self
    }

    /// Set explicit y limits.
    pub fn ylim(&mut self, lo: f64, hi: f64) -> &mut Self {
        self.panel.y.lim = Some((lo, hi));
        self
    }

    /// Show a legend for labelled artists.
    pub fn legend(&mut self) -> &mut Self {
        self.panel.legend = Legend {
            show: true,
            loc: "best".to_string(),
            family: self.panel.font_family.clone(),
            fontsize: 10.0,
            title_fontsize: 11.0,
            ncol: 1,
            frameon: true,
            order: self.artist_labels(),
            ..Default::default()
        };
        self
    }

    fn artist_labels(&self) -> Vec<String> {
        let mut entries: Vec<(bool, String)> = self
            .sequence
            .iter()
            .filter_map(|artist| match *artist {
                LastArtist::Series(index) => self
                    .panel
                    .series
                    .get(index)
                    .map(|artist| (false, artist.label.as_str())),
                LastArtist::Scatter(index) => self
                    .panel
                    .scatter
                    .get(index)
                    .map(|artist| (false, artist.label.as_str())),
                LastArtist::Bar(index) => self
                    .panel
                    .bars
                    .get(index)
                    .map(|artist| (true, artist.label.as_str())),
                LastArtist::Band(index) => self
                    .panel
                    .bands
                    .get(index)
                    .map(|artist| (false, artist.label.as_str())),
                LastArtist::Patch(index) => self
                    .panel
                    .patches
                    .get(index)
                    .map(|artist| (false, artist.label.as_str())),
                LastArtist::Collection(index) => self
                    .panel
                    .collections
                    .get(index)
                    .map(|artist| (false, artist.label.as_str())),
            })
            .filter(|(_, label)| !label.is_empty())
            .map(|(is_bar, label)| (is_bar, label.to_string()))
            .collect();
        // Matplotlib lists bar containers after the other artists, even when
        // the bars were added first.
        entries.sort_by_key(|(is_bar, _)| *is_bar);
        entries.into_iter().map(|(_, label)| label).collect()
    }

    /// Toggle the grid on both axes.
    pub fn grid(&mut self, show: bool) -> &mut Self {
        self.panel.grid.show = show;
        self.panel.grid.axis = "both".to_string();
        self
    }
}
