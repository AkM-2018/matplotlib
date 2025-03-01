"""
Routines to adjust subplot params so that subplots are
nicely fit in the figure. In doing so, only axis labels, tick labels, axes
titles and offsetboxes that are anchored to axes are currently considered.

Internally, this module assumes that the margins (left_margin, etc.) which are
differences between ax.get_tightbbox and ax.bbox are independent of axes
position. This may fail if Axes.adjustable is datalim. Also, This will fail
for some cases (for example, left or right margin is affected by xlabel).
"""

import numpy as np

from matplotlib import _api, docstring, rcParams
from matplotlib.font_manager import FontProperties
from matplotlib.transforms import TransformedBbox, Bbox


def _auto_adjust_subplotpars(
        fig, renderer, nrows_ncols, num1num2_list, subplot_list,
        ax_bbox_list=None, pad=1.08, h_pad=None, w_pad=None, rect=None):
    """
    Return a dict of subplot parameters to adjust spacing between subplots
    or ``None`` if resulting axes would have zero height or width.

    Note that this function ignores geometry information of subplot
    itself, but uses what is given by the *nrows_ncols* and *num1num2_list*
    parameters.  Also, the results could be incorrect if some subplots have
    ``adjustable=datalim``.

    Parameters
    ----------
    nrows_ncols : tuple[int, int]
        Number of rows and number of columns of the grid.
    num1num2_list : list[int]
        List of numbers specifying the area occupied by the subplot
    subplot_list : list of subplots
        List of subplots that will be used to calculate optimal subplot_params.
    pad : float
        Padding between the figure edge and the edges of subplots, as a
        fraction of the font size.
    h_pad, w_pad : float
        Padding (height/width) between edges of adjacent subplots, as a
        fraction of the font size.  Defaults to *pad*.
    rect : tuple[float, float, float, float]
        [left, bottom, right, top] in normalized (0, 1) figure coordinates.
    """
    rows, cols = nrows_ncols

    font_size_inches = (
        FontProperties(size=rcParams["font.size"]).get_size_in_points() / 72)
    pad_inches = pad * font_size_inches
    vpad_inches = h_pad * font_size_inches if h_pad is not None else pad_inches
    hpad_inches = w_pad * font_size_inches if w_pad is not None else pad_inches

    if len(num1num2_list) != len(subplot_list) or len(subplot_list) == 0:
        raise ValueError

    if rect is None:
        margin_left = margin_bottom = margin_right = margin_top = None
    else:
        margin_left, margin_bottom, _right, _top = rect
        margin_right = 1 - _right if _right else None
        margin_top = 1 - _top if _top else None

    vspaces = np.zeros((rows + 1, cols))
    hspaces = np.zeros((rows, cols + 1))

    if ax_bbox_list is None:
        ax_bbox_list = [
            Bbox.union([ax.get_position(original=True) for ax in subplots])
            for subplots in subplot_list]

    for subplots, ax_bbox, (num1, num2) in zip(subplot_list,
                                               ax_bbox_list,
                                               num1num2_list):
        if all(not ax.get_visible() for ax in subplots):
            continue

        bb = []
        for ax in subplots:
            if ax.get_visible():
                try:
                    bb += [ax.get_tightbbox(renderer, for_layout_only=True)]
                except TypeError:
                    bb += [ax.get_tightbbox(renderer)]

        tight_bbox_raw = Bbox.union(bb)
        tight_bbox = TransformedBbox(tight_bbox_raw,
                                     fig.transFigure.inverted())

        row1, col1 = divmod(num1, cols)
        row2, col2 = divmod(num2, cols)

        for row_i in range(row1, row2 + 1):
            hspaces[row_i, col1] += ax_bbox.xmin - tight_bbox.xmin  # left
            hspaces[row_i, col2 + 1] += tight_bbox.xmax - ax_bbox.xmax  # right
        for col_i in range(col1, col2 + 1):
            vspaces[row1, col_i] += tight_bbox.ymax - ax_bbox.ymax  # top
            vspaces[row2 + 1, col_i] += ax_bbox.ymin - tight_bbox.ymin  # bot.

    fig_width_inch, fig_height_inch = fig.get_size_inches()

    # margins can be negative for axes with aspect applied, so use max(, 0) to
    # make them nonnegative.
    if not margin_left:
        margin_left = (max(hspaces[:, 0].max(), 0)
                       + pad_inches / fig_width_inch)
        suplabel = fig._supylabel
        if suplabel and suplabel.get_in_layout():
            rel_width = fig.transFigure.inverted().transform_bbox(
                suplabel.get_window_extent(renderer)).width
            margin_left += rel_width + pad_inches / fig_width_inch

    if not margin_right:
        margin_right = (max(hspaces[:, -1].max(), 0)
                        + pad_inches / fig_width_inch)
    if not margin_top:
        margin_top = (max(vspaces[0, :].max(), 0)
                      + pad_inches / fig_height_inch)
        if fig._suptitle and fig._suptitle.get_in_layout():
            rel_height = fig.transFigure.inverted().transform_bbox(
                fig._suptitle.get_window_extent(renderer)).height
            margin_top += rel_height + pad_inches / fig_height_inch
    if not margin_bottom:
        margin_bottom = (max(vspaces[-1, :].max(), 0)
                         + pad_inches / fig_height_inch)
        suplabel = fig._supxlabel
        if suplabel and suplabel.get_in_layout():
            rel_height = fig.transFigure.inverted().transform_bbox(
                suplabel.get_window_extent(renderer)).height
            margin_bottom += rel_height + pad_inches / fig_height_inch

    if margin_left + margin_right >= 1:
        _api.warn_external('Tight layout not applied. The left and right '
                           'margins cannot be made large enough to '
                           'accommodate all axes decorations. ')
        return None
    if margin_bottom + margin_top >= 1:
        _api.warn_external('Tight layout not applied. The bottom and top '
                           'margins cannot be made large enough to '
                           'accommodate all axes decorations. ')
        return None

    kwargs = dict(left=margin_left,
                  right=1 - margin_right,
                  bottom=margin_bottom,
                  top=1 - margin_top)

    if cols > 1:
        hspace = hspaces[:, 1:-1].max() + hpad_inches / fig_width_inch
        # axes widths:
        h_axes = (1 - margin_right - margin_left - hspace * (cols - 1)) / cols
        if h_axes < 0:
            _api.warn_external('Tight layout not applied. tight_layout '
                               'cannot make axes width small enough to '
                               'accommodate all axes decorations')
            return None
        else:
            kwargs["wspace"] = hspace / h_axes
    if rows > 1:
        vspace = vspaces[1:-1, :].max() + vpad_inches / fig_height_inch
        v_axes = (1 - margin_top - margin_bottom - vspace * (rows - 1)) / rows
        if v_axes < 0:
            _api.warn_external('Tight layout not applied. tight_layout '
                               'cannot make axes height small enough to '
                               'accommodate all axes decorations')
            return None
        else:
            kwargs["hspace"] = vspace / v_axes

    return kwargs


@_api.deprecated("3.5")
@docstring.copy(_auto_adjust_subplotpars)
def auto_adjust_subplotpars(
        fig, renderer, nrows_ncols, num1num2_list, subplot_list,
        ax_bbox_list=None, pad=1.08, h_pad=None, w_pad=None, rect=None):
    num1num2_list = [
        (n1, n1 if n2 is None else n2) for n1, n2 in num1num2_list]
    return _auto_adjust_subplotpars(
        fig, renderer, nrows_ncols, num1num2_list, subplot_list,
        ax_bbox_list, pad, h_pad, w_pad, rect)


def get_renderer(fig):
    if fig._cachedRenderer:
        return fig._cachedRenderer
    else:
        canvas = fig.canvas
        if canvas and hasattr(canvas, "get_renderer"):
            return canvas.get_renderer()
        else:
            from . import backend_bases
            return backend_bases._get_renderer(fig)


def get_subplotspec_list(axes_list, grid_spec=None):
    """
    Return a list of subplotspec from the given list of axes.

    For an instance of axes that does not support subplotspec, None is inserted
    in the list.

    If grid_spec is given, None is inserted for those not from the given
    grid_spec.
    """
    subplotspec_list = []
    for ax in axes_list:
        axes_or_locator = ax.get_axes_locator()
        if axes_or_locator is None:
            axes_or_locator = ax

        if hasattr(axes_or_locator, "get_subplotspec"):
            subplotspec = axes_or_locator.get_subplotspec()
            subplotspec = subplotspec.get_topmost_subplotspec()
            gs = subplotspec.get_gridspec()
            if grid_spec is not None:
                if gs != grid_spec:
                    subplotspec = None
            elif gs.locally_modified_subplot_params():
                subplotspec = None
        else:
            subplotspec = None

        subplotspec_list.append(subplotspec)

    return subplotspec_list


def get_tight_layout_figure(fig, axes_list, subplotspec_list, renderer,
                            pad=1.08, h_pad=None, w_pad=None, rect=None):
    """
    Return subplot parameters for tight-layouted-figure with specified padding.

    Parameters
    ----------
    fig : Figure
    axes_list : list of Axes
    subplotspec_list : list of `.SubplotSpec`
        The subplotspecs of each axes.
    renderer : renderer
    pad : float
        Padding between the figure edge and the edges of subplots, as a
        fraction of the font size.
    h_pad, w_pad : float
        Padding (height/width) between edges of adjacent subplots.  Defaults to
        *pad*.
    rect : tuple[float, float, float, float], optional
        (left, bottom, right, top) rectangle in normalized figure coordinates
        that the whole subplots area (including labels) will fit into.
        Defaults to using the entire figure.

    Returns
    -------
    subplotspec or None
        subplotspec kwargs to be passed to `.Figure.subplots_adjust` or
        None if tight_layout could not be accomplished.
    """

    subplot_list = []
    nrows_list = []
    ncols_list = []
    ax_bbox_list = []

    # Multiple axes can share same subplot_interface (e.g., axes_grid1); thus
    # we need to join them together.
    subplot_dict = {}

    subplotspec_list2 = []

    for ax, subplotspec in zip(axes_list, subplotspec_list):
        if subplotspec is None:
            continue

        subplots = subplot_dict.setdefault(subplotspec, [])

        if not subplots:
            myrows, mycols, _, _ = subplotspec.get_geometry()
            nrows_list.append(myrows)
            ncols_list.append(mycols)
            subplotspec_list2.append(subplotspec)
            subplot_list.append(subplots)
            ax_bbox_list.append(subplotspec.get_position(fig))

        subplots.append(ax)

    if len(nrows_list) == 0 or len(ncols_list) == 0:
        return {}

    max_nrows = max(nrows_list)
    max_ncols = max(ncols_list)

    num1num2_list = []
    for subplotspec in subplotspec_list2:
        rows, cols, num1, num2 = subplotspec.get_geometry()
        div_row, mod_row = divmod(max_nrows, rows)
        div_col, mod_col = divmod(max_ncols, cols)
        if mod_row != 0:
            _api.warn_external('tight_layout not applied: number of rows '
                               'in subplot specifications must be '
                               'multiples of one another.')
            return {}
        if mod_col != 0:
            _api.warn_external('tight_layout not applied: number of '
                               'columns in subplot specifications must be '
                               'multiples of one another.')
            return {}

        row1, col1 = divmod(num1, cols)
        row2, col2 = divmod(num2, cols)

        num1num2_list.append((row1 * div_row * max_ncols + col1 * div_col,
                              ((row2 + 1) * div_row - 1) * max_ncols +
                              (col2 + 1) * div_col - 1))

    kwargs = _auto_adjust_subplotpars(fig, renderer,
                                      nrows_ncols=(max_nrows, max_ncols),
                                      num1num2_list=num1num2_list,
                                      subplot_list=subplot_list,
                                      ax_bbox_list=ax_bbox_list,
                                      pad=pad, h_pad=h_pad, w_pad=w_pad)

    # kwargs can be none if tight_layout fails...
    if rect is not None and kwargs is not None:
        # if rect is given, the whole subplots area (including
        # labels) will fit into the rect instead of the
        # figure. Note that the rect argument of
        # *auto_adjust_subplotpars* specify the area that will be
        # covered by the total area of axes.bbox. Thus we call
        # auto_adjust_subplotpars twice, where the second run
        # with adjusted rect parameters.

        left, bottom, right, top = rect
        if left is not None:
            left += kwargs["left"]
        if bottom is not None:
            bottom += kwargs["bottom"]
        if right is not None:
            right -= (1 - kwargs["right"])
        if top is not None:
            top -= (1 - kwargs["top"])

        kwargs = _auto_adjust_subplotpars(fig, renderer,
                                          nrows_ncols=(max_nrows, max_ncols),
                                          num1num2_list=num1num2_list,
                                          subplot_list=subplot_list,
                                          ax_bbox_list=ax_bbox_list,
                                          pad=pad, h_pad=h_pad, w_pad=w_pad,
                                          rect=(left, bottom, right, top))

    return kwargs
