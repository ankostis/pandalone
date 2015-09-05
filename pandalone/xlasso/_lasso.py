#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
The high-level functionality, the filtering and recursive :term:`lassoing`.

Prefer accessing the public members from the parent module.

.. currentmodule:: pandalone.xlasso
"""

from __future__ import unicode_literals

from collections import namedtuple, OrderedDict
from copy import deepcopy
import inspect
import logging
import textwrap

from future.backports import ChainMap
from future.utils import iteritems
from past.builtins import basestring
from toolz import dicttoolz as dtz

import itertools as itt
import numpy as np

from . import _parse
from ..utils import as_list
from ._capture import resolve_capture_rect


log = logging.getLogger(__name__)


class SheetsFactory(object):
    """
    A caching-store of :class:`ABCSheet` instances, serving them based on (workbook, sheet) IDs, optionally creating them from backends.

    :ivar dict _cached_sheets: 
            A cache of all _Spreadsheets accessed so far, 
            keyed by multiple keys generated by :meth:`_derive_sheet_keys`.
    :ivar ABCSheet _current_sheet:
            The last used sheet, used when unspecified by the :term:`xl-ref`.

    - To avoid opening non-trivial workbooks, use the :meth:`add_sheet()` 
      to pre-populate this cache with them.

    - The last sheet added becomes the *current-sheet*, and will be 
      served when :term:`xl-ref` does not specify any workbook and sheet.

      .. Tip::
          For the simplest API usage, try this::

              >>> sf = SheetsFactory()
              >>> sf.add_sheet(some_sheet)              # doctest: +SKIP
              >>> lasso('A1:C3(U)', sf)                 # doctest: +SKIP

    - The *current-sheet* is served only when wokbook-id is `None`, that is,
      the id-pair ``('foo.xlsx', None)`` does not hit it, so those ids 
      are send to the cache as they are.

    - To add another backend, modify the opening-sheets logic (ie clipboard), 
      override :meth:`_open_sheet()`.

    - It is a resource-manager for contained sheets, wo it can be used wth 
      a `with` statement.

    """

    def __init__(self, current_sheet=None):
        self._current_sheet = current_sheet
        self._cached_sheets = {}

    def _cache_get(self, key):
        wb, sh = key
        if wb in self._cached_sheets:
            shs = self._cached_sheets[wb]
            return shs.get(sh, None)

    def _cache_put(self, key, sheet):
        wb, sh = key
        if wb in self._cached_sheets:
            sh_dict = self._cached_sheets[wb]
        else:
            sh_dict = self._cached_sheets[wb] = {}
        sh_dict[sh] = sheet

    def _build_sheet_key(self, wb, sh):
        assert wb is not None, (wb, sh)
        return (wb, sh)

    def _derive_sheet_keys(self, sheet,  wb_ids=None, sh_ids=None):
        """
        Retuns the product of user-specified and sheet-internal keys.

        :param wb_ids:
                a single or a sequence of extra workbook-ids (ie: file, url)
        :param sh_ids:
                a single or sequence of extra sheet-ids (ie: name, index, None)
        """
        wb_id, sh_ids2 = sheet.get_sheet_ids()
        assert wb_id is not None, (wb_id, sh_ids2)
        wb_ids = [wb_id] + as_list(wb_ids)
        sh_ids = sh_ids2 + as_list(sh_ids)

        key_pairs = itt.product(wb_ids, sh_ids)
        keys = list(set(self._build_sheet_key(*p)
                        for p in key_pairs
                        if p[0]))
        assert keys, (keys, sheet,  wb_ids, sh_ids)

        return keys

    def _close_sheet(self, key):
        sheet = self._cache_get(key)
        if sheet:
            sheet._close()
            for sh_dict in self._cached_sheets.values():
                for sh_id, sh in list(iteritems(sh_dict)):
                    if sh is sheet:
                        del sh_dict[sh_id]
            if self._current_sheet is sheet:
                self._current_sheet = None

    def close(self):
        """Closes all contained sheets and empties cache."""
        for sh_dict in self._cached_sheets.values():
            for sh in sh_dict.values():
                sh._close_all()
        self._cached_sheets = {}
        self._current_sheet = None

    def add_sheet(self, sheet, wb_ids=None, sh_ids=None,
                  no_current=False):
        """
        Updates cache and (optionally) `_current_sheet`.

        :param wb_ids:
                a single or sequence of extra workbook-ids (ie: file, url)
        :param sh_ids:
                a single or sequence of extra sheet-ids (ie: name, index, None)
        """
        assert sheet, (sheet, wb_ids, sh_ids)
        keys = self._derive_sheet_keys(sheet, wb_ids, sh_ids)
        for k in keys:
            old_sheet = self._cache_get(k)
            if old_sheet and old_sheet is not sheet:
                self._close_sheet(k)
            self._cache_put(k, sheet)
        if not no_current:
            self._current_sheet = sheet

    def fetch_sheet(self, wb_id, sheet_id, opts={}):
        csheet = self._current_sheet
        if wb_id is None:
            if not csheet:
                msg = "No current-sheet exists yet!. Specify a Workbook."
                raise ValueError(msg)

            if sheet_id is None:
                return csheet

            wb_id, c_sh_ids = csheet.get_sheet_ids()
            assert wb_id is not None, (csheet, c_sh_ids)

            key = self._build_sheet_key(wb_id, sheet_id)
            sheet = self._cache_get(key)

            if not sheet:
                sheet = csheet.open_sibling_sheet(sheet_id, opts)
                assert sheet, (wb_id, sheet_id, opts)
                self.add_sheet(sheet, wb_id, sheet_id)
        else:
            key = self._build_sheet_key(wb_id, sheet_id)
            sheet = self._cache_get(key)
            if not sheet:
                sheet = self._open_sheet(wb_id, sheet_id, opts)
                assert sheet, (wb_id, sheet_id, opts)
                self.add_sheet(sheet, wb_id, sheet_id)

        return sheet

    def _open_sheet(self, wb_id, sheet_id, opts):
        """OVERRIDE THIS to change backend."""
        from . import _xlrd
        return _xlrd.open_sheet(wb_id, sheet_id, opts)

    def __enter__(self):
        return self

    def __exit__(self, typ, value, traceback):
        self.close()


Lasso = namedtuple('Lasso',
                   ('xl_ref', 'url_file', 'sh_name',
                    'st_edge', 'nd_edge', 'exp_moves',
                    'call_spec',
                    'sheet', 'st', 'nd', 'values', 'base_coords',
                    'opts'))
"""
All the fields used by the algorithm, populated stage-by-stage by :class:`Ranger`.

:param str xl_ref:
        The full url, populated on parsing.
:param str sh_name:
        Parsed sheet name (or index, but still as string), populated on parsing.
:param Edge st_edge:
        The 1st edge, populated on parsing.
:param Edge nd_edge:
        The 2nd edge, populated on parsing.
:param Coords st:
        The top-left targeted coords of the :term:`capture-rect`, 
        populated on :term:`capturing`.`
:param Coords nd:
        The bottom-right targeted coords of the :term:`capture-rect`, 
        populated on :term:`capturing`
:param ABCSheet sheet:
        The fetched from factory or ranger's current sheet, populated 
        after :term:`capturing` before reading.
:param values:
        The excel's table-values captured by the :term:`lasso`, 
        populated after reading updated while applying :term:`filters`. 
:param dict or ChainMap opts:
        - Before `parsing`, they are just any 'opts' dict found in the 
          :term:`filters`. 
        - After *parsing, a 2-map ChainMap with :attr:`Ranger.base_opts` and
          options extracted from *filters* on top.
"""


Lasso.__new__.__defaults__ = (None,) * len(Lasso._fields)
"""Make :class:`Lasso` construct with all missing fields as `None`."""


def _Lasso_to_edges_str(lasso):
    st = lasso.st_edge if lasso.st_edge else ''
    nd = lasso.nd_edge if lasso.nd_edge else ''
    s = st if st and not nd else '%s:%s' % (st, nd)
    exp = ':%s' % lasso.exp_moves.upper() if lasso.exp_moves else ''
    return s + exp


class Ranger(object):
    """
    The director-class that performs all stages required for "throwing the lasso" around rect-values.

    Use it when you need to have total control of the procedure and 
    configuration parameters, since no defaults are assumed.

    The :meth:`do_lasso()` does the job.

    :ivar SheetsFactory sheets_factory:
            Factory of sheets from where to parse rect-values; does not 
            close it in the end.
            Maybe `None`, but :meth:`do_lasso()` will scream unless invoked 
            with a `context_lasso` arg containing a concrete :class:`ABCSheet`.
    :ivar dict base_opts: 
            The :term:`opts` that are deep-copied and used as the defaults 
            for every :meth:`do_lasso()`, whether invoked directly or 
            recursively by :meth:`recursive_filter()`.
            If unspecified, no opts are used, but this attr is set to an 
            empty dict.
            See :func:`get_default_opts()`.
    :ivar dict or None available_filters: 
            No filters exist if unspecified. 
            See :func:`get_default_filters()`.
    :ivar Lasso intermediate_lasso:
            A ``('stage', Lasso)`` pair with the last :class:`Lasso` instance 
            produced during the last execution of the :meth:`do_lasso()`.
            Used for inspecting/debuging.
    :ivar _context_lasso_fields:
            The name of the fields taken from `context_lasso` arg of 
            :meth:`do_lasso()`, when the parsed ones are `None`.
            Needed for recursive invocations, see :meth:`recursive_filter`.
    """

    _context_lasso_fields = ['sheet', 'st', 'nd', 'base_coords']

    def __init__(self, sheets_factory,
                 base_opts=None, available_filters=None):
        self.sheets_factory = sheets_factory
        if base_opts is None:
            base_opts = {}
        self.base_opts = base_opts
        self.available_filters = available_filters
        self.intermediate_lasso = None

    def _relasso(self, lasso, stage, **kwds):
        """Replace lasso-values and updated :attr:`intermediate_lasso`."""
        lasso = lasso._replace(**kwds)
        self.intermediate_lasso = (stage, lasso)

        return lasso

    def _make_call(self, lasso, func_name, args, kwds):
        def parse_avail_func_rec(func, desc=None):
            if not desc:
                desc = func.__doc__
            return func, desc

        # Just to update intermediate_lasso.
        lasso = self._relasso(lasso, func_name)

        lax = lasso.opts.get('lax', False)
        verbose = lasso.opts.get('verbose', False)
        func, func_desc = '', ''
        try:
            func_rec = self.available_filters[func_name]
            func, func_desc = parse_avail_func_rec(**func_rec)
            lasso = func(self, lasso, *args, **kwds)
            assert isinstance(lasso, Lasso), (func_name, lasso)
        except Exception as ex:
            if verbose:
                func_desc = _build_call_help(func_name, func, func_desc)
            msg = "While invoking(%s, %s, %s): %s%s"
            help_msg = func_desc if verbose else ''
            if lax:
                log.warning(
                    msg, func_name, args, kwds, ex, help_msg, exc_info=1)
            else:
                raise ValueError(msg % (func_name, args, kwds, ex, help_msg))

        return lasso

    def pipe_filter(self, lasso, *pipe):
        """
        Apply all call-specifiers one after another on the captured values.

        :param list pipe: the call-specifiers
        """

        for call_spec_values in pipe:
            call_spec = _parse.parse_call_spec(call_spec_values)
            lasso = self._make_call(lasso, *call_spec)

        return lasso

    def recursive_filter(self, lasso, include=None, exclude=None, depth=-1):
        """
        Recursively expand any :term:`xl-ref` strings found by treating values as mappings (dicts, df, series) and/or nested lists.

        - The `include`/`exclude` filter args work only for dict-like objects
          with ``items()`` or ``iteritems()`` and indexing methods, 
          i.e. Mappings, series and dataframes.

          - If no filter arg specified, expands for all keys. 
          - If only `include` specified, rejects all keys not explicitly 
            contained in this filter arg.
          - If only `exclude` specified, expands all keys not explicitly 
            contained in this filter arg.
          - When both `include`/`exclude` exist, only those explicitely 
            included are accepted, unless also excluded.

        - Lower the :mod:`logging` level to see other than syntax-errors on
          recursion reported on :data:`log`.
        - Only those in :attr:`Ranger._context_lasso_fields` are passed 
          recursively.

        :param list or str include:
                Items to include in the recursive-search.
                See descritpion above.
        :param list or str exclude:
                Items to include in the recursive-search.
                See descritpion above.
        :param int or None depth:
                How deep to dive into nested structures for parsing xl-refs.
                If `< 0`, no limit. If 0, stops completely.
        """
        include = include and as_list(include)
        exclude = exclude and as_list(exclude)

        def verbose(msg):
            if lasso.opts.get('verbose', False):
                msg = '%s \n    @Lasso: %s' % (msg, lasso)
            return msg

        def is_included(key):
            ok = not include or key in include
            ok &= not exclude or key not in exclude
            return ok

        def new_base_coords(base_coords, cdepth, i):
            if base_coords:
                if cdepth == 0:
                    base_coords = base_coords._replace(row=i)
                elif cdepth == 1:
                    base_coords = base_coords._replace(col=i)
            return base_coords

        def invoke_recursively(vals, base_coords, cdepth):
            context = dtz.keyfilter(lambda k: k in self._context_lasso_fields,
                                    lasso._asdict())
            context['base_coords'] = base_coords
            try:
                rlasso = self.do_lasso(vals, **context)
                vals = rlasso and rlasso.values
            except SyntaxError as ex:
                msg = "Skipped non xl-ref(%s) due to: %s"
                log.debug(msg, vals, ex)
            except Exception as ex:
                loc = lasso.sheet.get_sheet_ids() if lasso.sheet else ()
                if lasso.base_coords:
                    loc += (lasso.base_coords,)
                msg = "Lassoing  xl-ref(%s) at loc(%s) stopped due to: \n  %s"
                msg %= (vals, loc, ex)
                raise ValueError(verbose(msg))
            return vals

        def dive_list(vals, base_coords, cdepth):
            if isinstance(vals, basestring):
                vals = invoke_recursively(vals, base_coords, cdepth)
            elif isinstance(vals, list):
                for i, v in enumerate(vals):
                    nbc = new_base_coords(base_coords, cdepth, i)
                    vals[i] = dive_indexed(v, nbc, cdepth + 1)

            return vals

        def dive_indexed(vals, base_coords, cdepth):
            if cdepth != depth:
                dived = False
                try:
                    items = iteritems(vals)
                except:
                    pass  # Just to avoid chained ex.
                else:
                    for i, (k, v) in enumerate(items):
                        # Dict is not ordered, so cannot locate `base_coords`!
                        if is_included(k):
                            nbc = (None
                                   if isinstance(vals, dict)
                                   else new_base_coords(base_coords, cdepth, i))
                            vals[k] = dive_indexed(v, nbc, cdepth + 1)
                    dived = True
                if not dived:
                    vals = dive_list(vals, base_coords, cdepth)

            return vals

        values = dive_indexed(lasso.values, lasso.st, 0)

        return lasso._replace(values=values)

    def _make_init_Lasso(self, **context_kwds):
        """Creates the lasso to be used for each new :meth:`do_lasso()` invocation."""
        context_kwds['opts'] = ChainMap(deepcopy(self.base_opts))
        init_lasso = Lasso(**context_kwds)

        return init_lasso

    def _parse_and_merge_with_context(self, xlref, init_lasso):
        """
        Merges xl-ref parsed-parsed_fields with `init_lasso`, reporting any errors.

        :param Lasso init_lasso: 
                Default values to be overridden by non-nulls.
                Note that ``init_lasso.opts`` must be a `ChainMap`,
                as returned by :math:`_make_init_Lasso()`. 

        :return: a Lasso with any non `None` parsed-fields updated
        """
        assert isinstance(init_lasso.opts, ChainMap), init_lasso

        try:
            parsed_fields = _parse.parse_xlref(xlref)
            parsed_opts = parsed_fields.pop('opts', None)
            if parsed_opts:
                init_lasso.opts.maps.insert(0, parsed_opts)
            filled_fields = dtz.valfilter(lambda v: v is not None,
                                          parsed_fields)
            init_lasso = init_lasso._replace(**filled_fields)
        except SyntaxError:
            raise
        except Exception as ex:
            msg = "Parsing xl-ref(%r) failed due to: %s"
            log.debug(msg, xlref, ex, exc_info=1)
            # raise fututils.raise_from(ValueError(msg % (xlref, ex)), ex) see GH
            # 141
            raise ValueError(msg % (xlref, ex))

        return init_lasso

    def _fetch_sheet_from_lasso(self, sheet, url_file, sh_name, opts):
        if sheet and url_file is None:
            if sh_name is not None:
                sheet = sheet.open_sibling_sheet(sh_name, opts)
                if sheet and self.sheets_factory:
                    self.sheets_factory.add_sheet(sheet,
                                                  wb_ids=url_file,
                                                  sh_ids=sh_name)
            return sheet

    def _open_sheet(self, lasso):
        try:
            sheet = self._fetch_sheet_from_lasso(lasso.sheet,
                                                 lasso.url_file, lasso.sh_name,
                                                 lasso.opts)
            if not sheet:
                if not self.sheets_factory:
                    msg = "The xl-ref(%r) specifies 'url-file` part but Ranger has no sheet-factory!"
                    raise Exception(msg % lasso.xl_ref)
                sheet = self.sheets_factory.fetch_sheet(
                    lasso.url_file, lasso.sh_name,
                    lasso.opts)  # Maybe context had a Sheet already.
        except Exception as ex:
            msg = "Loading sheet([%s]%s) failed due to: %s"
            raise ValueError(msg % (lasso.url_file, lasso.sh_name, ex))
        return sheet

    def _resolve_capture_rect(self, lasso, sheet):
        try:
            st, nd = resolve_capture_rect(sheet.get_states_matrix(),
                                          sheet.get_margin_coords(),
                                          lasso.st_edge,
                                          lasso.nd_edge,
                                          lasso.exp_moves,
                                          lasso.base_coords)
        except Exception as ex:
            msg = "Resolving capture-rect(%r) failed due to: %s"
            raise ValueError(msg % (_Lasso_to_edges_str(lasso), ex))
        return st, nd

    def do_lasso(self, xlref, **context_kwds):
        """
        The director-method that does all the job of hrowing a :term:`lasso`
        around spreadsheet's rect-regions according to :term:`xl-ref`.

        :param str xlref:
            a string with the :term:`xl-ref` format::

                <url_file>#<sheet>!<1st_edge>:<2nd_edge>:<expand><js_filt>

            i.e.::

                file:///path/to/file.xls#sheet_name!UPT8(LU-):_.(D+):LDL1{"dims":1}

        :param Lasso context_kwds: 
                Default :class:`Lasso` fields in case parsed ones are `None` 
                Only those in :attr:`_context_lasso_fields` are taken 
                into account.
                Utilized  by :meth:`recursive_filter()`.
        :return: 
                The final :class:`Lasso` with captured & filtered values.
        :rtype: Lasso
        """
        if not isinstance(xlref, basestring):
            raise ValueError("Expected a string as `xl-ref`: %s" % xlref)
        self.intermediate_lasso = None

        lasso = self._make_init_Lasso(**context_kwds)
        lasso = self._relasso(lasso, 'context')

        lasso = self._parse_and_merge_with_context(xlref, lasso)
        lasso = self._relasso(lasso, 'parse')

        sheet = self._open_sheet(lasso)
        lasso = self._relasso(lasso, 'open', sheet=sheet)

        st, nd = self._resolve_capture_rect(lasso, sheet)
        lasso = self._relasso(lasso, 'capture', st=st, nd=nd)

        values = sheet.read_rect(st, nd)
        lasso = self._relasso(lasso, 'read_rect', values=values)

        if lasso.call_spec:
            try:
                lasso = self._make_call(lasso, *lasso.call_spec)
                # relasso(values) invoked internally.
            except Exception as ex:
                msg = "Filtering xl-ref(%r) failed due to: %s"
                raise ValueError(msg % (lasso.xl_ref, ex))

        return lasso

###############
# FILTER-DEFS
###############


def _build_call_help(name, func, desc):
    sig = func and inspect.formatargspec(*inspect.getfullargspec(func))
    desc = textwrap.indent(textwrap.dedent(desc), '    ')
    return '\n\nFilter: %s%s:\n%s' % (name, sig, desc)


def _classify_rect_shape(st, nd):
    """
    Identifies rect from its edge-coordinates (row, col, 2d-table)..

    :param Coords st:
            the top-left edge of capture-rect, inclusive
    :param Coords or None nd:
            the bottom-right edge of capture-rect, inclusive
    :return: 
            in int based on the input like that:

            - 0: only `st` given 
            - 1: `st` and `nd` point the same cell 
            - 2: row 
            - 3: col 
            - 4: 2d-table 

    Examples::

        >>> _classify_rect_shape((1,1), None)
        0
        >>> _classify_rect_shape((2,2), (2,2))
        1
        >>> _classify_rect_shape((2,2), (2,20))
        2
        >>> _classify_rect_shape((2,2), (20,2))
        3
        >>> _classify_rect_shape((2,2), (20,20))
        4
    """
    if nd is None:
        return 0
    rows = nd[0] - st[0]
    cols = nd[1] - st[1]
    return 1 + bool(cols) + 2 * bool(rows)


def _decide_ndim_by_rect_shape(shape_idx, ndims_list):
    return ndims_list[shape_idx]


def _updim(values, new_ndim):
    """
    Append trivial dimensions to the left.

    :param values:      The scalar ot 2D-results of :meth:`Sheet.read_rect()`
    :param int new_dim: The new dimension the result should have
    """
    new_shape = (1,) * (new_ndim - values.ndim) + values.shape
    return values.reshape(new_shape)


def _downdim(values, new_ndim):
    """
    Squeeze it, and then flatten it, before inflating it.

    :param values:       The scalar ot 2D-results of :meth:`Sheet.read_rect()`
    :param int new_dim: The new dimension the result should have
    """
    trivial_indxs = [i for i, d in enumerate(values.shape) if d == 1]
    offset = values.ndim - new_ndim
    trivial_ndims = len(trivial_indxs)
    if offset > trivial_ndims:
        values = values.flatten()
    elif offset == trivial_ndims:
        values = values.squeeze()
    else:
        for _, indx in zip(range(offset), trivial_indxs):
            values = values.squeeze(indx)

    return values


def _redim(values, new_ndim):
    """
    Reshapes the :term:`capture-rect` values of :func:`read_capture_rect()`.

    :param values:      The scalar ot 2D-results of :meth:`Sheet.read_rect()`
    :type values: (nested) list, *
    :param new_ndim: 
    :type int, (int, bool) or None new_ndim: 

    :return: reshaped values
    :rtype: list of lists, list, *


    Examples::

        >>> _redim([1, 2], 2)
        [[1, 2]]

        >>> _redim([[1, 2]], 1)
        [1, 2]

        >>> _redim([], 2)
        [[]]

        >>> _redim([[3.14]], 0)
        3.14

        >>> _redim([[11, 22]], 0)
        [11, 22]

        >>> arr = [[[11], [22]]]
        >>> arr == _redim(arr, None)
        True

        >>> _redim([[11, 22]], 0)
        [11, 22]
    """
    if new_ndim is None:
        return values

    values = np.asarray(values)
    try:
        new_ndim, transpose = new_ndim
        if transpose:
            values = values.T
    except:
        pass
    if new_ndim is not None:
        if values.ndim < new_ndim:
            values = _updim(values, new_ndim)
        elif values.ndim > new_ndim:
            values = _downdim(values, new_ndim)

    return values.tolist()


def xlwings_dims_call_spec():
    """A list :term:`call-spec` for :meth:`_redim_filter` :term:`filter` that imitates results of *xlwings* library."""
    return '["redim", [0, 1, 1, 1, 2]]'


def redim_filter(ranger, lasso,
                 scalar=None, cell=None, row=None, col=None, table=None):
    """
    Reshape and/or transpose captured values, depending on rect's shape.

    Each dimension might be a single int or None, or a pair [dim, transpose]. 
    """
    ndims_list = (scalar, cell, row, col, table)
    shape_idx = _classify_rect_shape(lasso.st, lasso.nd)
    new_ndim = _decide_ndim_by_rect_shape(shape_idx, ndims_list)
    values = lasso.values
    if new_ndim is not None:
        lasso = lasso._replace(values=_redim(values, new_ndim))

    return lasso


def get_default_filters(overrides=None):
    """
   The default available :term:`filters` used by :func:`lasso()` when constructing its internal :class:`Ranger`.

    :param dict or None overrides:
            Any items to update the default ones.

    :return: 
            a dict-of-dicts with 2 items: 

            - *func*: a function with args: ``(Ranger, Lasso, *args, **kwds)``
            - *desc*:  help-text replaced by ``func.__doc__`` if missing.

    :rtype: 
            dict
    """
    filters = {
        'pipe': {
            'func': Ranger.pipe_filter,
        },
        'recurse': {
            'func': Ranger.recursive_filter,
        },
        'redim': {
            'func': redim_filter,
        },
        'numpy': {
            'func': lambda ranger, lasso, * args, **kwds: lasso._replace(
                values=np.array(lasso.values, *args, **kwds)),
            'desc': np.array.__doc__,
        },
        'dict': {
            'func': lambda ranger, lasso, * args, **kwds: lasso._replace(
                values=dict(lasso.values, *args, **kwds)),
            'desc': dict.__doc__,
        },
        'odict': {
            'func': lambda ranger, lasso, * args, **kwds: lasso._replace(
                values=OrderedDict(lasso.values, *args, **kwds)),
            'desc': OrderedDict.__doc__,
        },
        'sorted': {
            'func': lambda ranger, lasso, * args, **kwds: lasso._replace(
                values=sorted(lasso.values, *args, **kwds)),
            'desc': sorted.__doc__,
        },
    }

    try:
        import pandas as pd
        from pandas.io import parsers, excel as pdexcel

        def _df_filter(ranger, lasso, *args, **kwds):
            values = lasso.values
            header = kwds.get('header', 'infer')
            if header == 'infer':
                header = kwds['header'] = 0 if kwds.get(
                    'names') is None else None
            if header is not None:
                values[header] = pdexcel._trim_excel_header(values[header])
            # , convert_float=True,
            parser = parsers.TextParser(values, **kwds)
            lasso = lasso._replace(values=parser.read())

            return lasso

        filters.update({
            'df': {
                'func': _df_filter,
                'desc': parsers.TextParser.__doc__,
            },
            'series': {
                'func': lambda ranger, lasso, *args, **kwds: pd.Series(OrderedDict(lasso.values),
                                                                       *args, **kwds),
                'desc': ("Converts a 2-columns list-of-lists into pd.Series.\n" +
                         pd.Series.__doc__),
            }
        })
    except ImportError as ex:
        msg = "The 'df' and 'series' filters were notinstalled, due to: %s"
        log.info(msg, ex)

    if overrides:
        filters.update(overrides)

    return filters


def get_default_opts(overrides=None):
    """
    Default :term:`opts` used by :func:`lasso()` when constructing its internal :class:`Ranger`.

    :param dict or None overrides:
            Any items to update the default ones.
    """
    opts = {
        'lax': False,
        'verbose': False,
        'read': {'on_demand': True, },
    }

    if overrides:
        opts.update(overrides)

    return opts


def make_default_Ranger(sheets_factory=None,
                        base_opts=None,
                        available_filters=None):
    """
    Makes a defaulted :class:`Ranger`.

    :param sheets_factory:
            Factory of sheets from where to parse rect-values; if unspecified, 
            a new :class:`SheetsFactory` is created.
            Remember to invoke its :meth:`SheetsFactory.close()` to clear
            resources from any opened sheets. 
    :param dict or None base_opts: 
            Default opts to affect the lassoing, to be merged with defaults; 
            uses :func:`get_default_opts()`.

            Read the code to be sure what are the available choices :-(. 
    :param dict or None available_filters: 
            The available :term:`filters` to specify a :term:`xl-ref`.
            Uses :func:`get_default_filters()` if unspecified.

    """
    return Ranger(sheets_factory or SheetsFactory(),
                  base_opts or get_default_opts(),
                  available_filters or get_default_filters())


def lasso(xlref,
          sheets_factory=None,
          base_opts=None,
          available_filters=None,
          return_lasso=False,
          **context_kwds):
    """
    High-level function to :term:`lasso` around spreadsheet's rect-regions 
    according to :term:`xl-ref` strings by using internally a :class:`Ranger` .

    :param str xlref:
        a string with the :term:`xl-ref` format::

            <url_file>#<sheet>!<1st_edge>:<2nd_edge>:<expand><js_filt>

        i.e.::

            file:///path/to/file.xls#sheet_name!UPT8(LU-):_.(D+):LDL1{"dims":1}

    :param sheets_factory:
            Factory of sheets from where to parse rect-values; if unspecified, 
            the new :class:`SheetsFactory` created is closed afterwards.
            Delegated to :func:`make_default_Ranger()`, so items override
            default ones; use a new :class:`Ranger` if that is not desired.
    :ivar dict or None base_opts: 
            Opts affecting the lassoing procedure that are deep-copied and used
            as the base-opts for every :meth:`Ranger.do_lasso()`, whether invoked 
            directly or recursively by :meth:`Ranger.recursive_filter()`. 
            Read the code to be sure what are the available choices. 
            Delegated to :func:`make_default_Ranger()`, so items override
            default ones; use a new :class:`Ranger` if that is not desired.
    :param dict or None available_filters: 
            Delegated to :func:`make_default_Ranger()`, so items override
            default ones; use a new :class:`Ranger` if that is not desired.
    :param bool return_lasso:
            If `True`, values are contained in the returned Lasso instance,
            along with all other artifacts of the :term:`lassoing` procedure.

            For more debugging help, create a :class:`Range` yourself and 
            inspect the :attr:`Ranger.intermediate_lasso`.
    :param Lasso context_kwds: 
            Default :class:`Lasso` fields in case parsed ones are `None`
            (i.e. you can specify the sheet like that).

    :return: 
            Either the captured & filtered values or the final :class:`Lasso`,
            depending on the `return_lassos` arg.
    """
    factory_is_mine = not sheets_factory
    if base_opts is None:
        base_opts = get_default_opts()
    if available_filters is None:
        available_filters = get_default_filters()

    try:
        ranger = make_default_Ranger(sheets_factory=sheets_factory,
                                     base_opts=base_opts,
                                     available_filters=available_filters)
        lasso = ranger.do_lasso(xlref, **context_kwds)
    finally:
        if factory_is_mine:
            ranger.sheets_factory.close()

    return lasso if return_lasso else lasso.values
