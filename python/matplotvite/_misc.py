"""GridSpec subclasses and small transform helpers."""
from ._artists import (
    Collection,
    EllipseCollection,
    EventCollection,
    LineCollection,
    PatchCollection,
    PathCollection,
    PolyCollection,
    RegularPolyCollection,
    patches,
)
from ._cm import (
    Colorizer,
    LightSource,
    ScalarMappable,
    _MColors,
    from_levels_and_colors,
    hsv_to_rgb,
    rgb_to_hsv,
)
from ._config import _Namespace
from ._core import (
    Normalize as _Normalize,
)
from ._helpers import (
    Affine2D,
    Path,
    TransformedPath,
    _Bbox,
    _CoordTransform,
    _IdentityTransform,
    _ignored,
    _Transform,
    cm,
)
from ._images import Colorbar, GridSpec, NonUniformImage
from ._plot_helpers import MarkerStyle
from ._png import _imread
from ._pyplot import colorbar
from ._ticker import _TransformedBbox


class GridSpecFromSubplotSpec(GridSpec):
    """A GridSpec rooted at an existing SubplotSpec."""

    def __init__(self, nrows, ncols, subplot_spec=None, **kwargs):
        super().__init__(nrows, ncols, **kwargs)
        self.subplot_spec = subplot_spec


def _offset_copy(trans, fig=None, x=0, y=0, units="inches", **kwargs):
    _ignored("mtransforms.offset_copy")
    return _Transform()


def _blended_transform_factory(x_transform, y_transform):
    """Combined transform: matplotvite only distinguishes data/axes/figure."""
    kinds = {getattr(t, "kind", None) for t in (x_transform, y_transform)}
    for kind in ("axes", "figure"):
        if kind in kinds:
            return _CoordTransform(kind)
    return _Transform()


mcolors = _MColors()
mcolors.ScalarMappable = ScalarMappable
mcolors.LightSource = LightSource
mcolors.rgb_to_hsv = rgb_to_hsv
mcolors.hsv_to_rgb = hsv_to_rgb
mcolors.Normalize = _Normalize
mcolors.from_levels_and_colors = from_levels_and_colors
mcolorbar = _Namespace(Colorbar=Colorbar, ColorbarBase=Colorbar)
# The gallery binds `matplotlib.colorbar` to this callable, so expose the
# classes on the function as well as in the standalone namespace.
colorbar.Colorbar = Colorbar
colorbar.ColorbarBase = Colorbar
cm.ScalarMappable = ScalarMappable
colors = mcolors
mpatches = patches
mpath = _Namespace(Path=Path, TransformedPath=TransformedPath)
path = mpath
mcollections = _Namespace(Collection=Collection, LineCollection=LineCollection,
                          PolyCollection=PolyCollection, PatchCollection=PatchCollection,
                          EventCollection=EventCollection, PathCollection=PathCollection,
                          RegularPolyCollection=RegularPolyCollection,
                          EllipseCollection=EllipseCollection)
collections = mcollections
markers = _Namespace(MarkerStyle=MarkerStyle)
mmarkers = markers
_INTERPD = {name: name for name in (
    "none", "nearest", "antialiased", "bilinear", "bicubic", "spline16",
    "spline36", "hanning", "hamming", "hermite", "kaiser", "quadric",
    "catrom", "gaussian", "lanczos", "blackman", "sinc", "bessel",
    "mitchell", "auto",
)}
image = _Namespace(imread=_imread, NonUniformImage=NonUniformImage,
                   _interpd_=_INTERPD)
colorizer = _Namespace(Colorizer=Colorizer)
mtransforms = _Namespace(Transform=_Transform, Affine2D=Affine2D, Bbox=_Bbox,
                         TransformedPath=TransformedPath,
                         BboxTransformTo=_Transform, IdentityTransform=_IdentityTransform,
                         ScaledTranslation=_Transform, TransformedBbox=_TransformedBbox,
                         blended_transform_factory=_blended_transform_factory,
                         offset_copy=_offset_copy)
transforms = mtransforms
