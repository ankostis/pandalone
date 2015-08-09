#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
Implements the *xlrd* backend of :term:`xl-ref` that reads in-file Excel-spreadsheets.

Prefer accessing the public members from the parent module.
"""

import datetime
from distutils.version import LooseVersion
import logging

from xlrd import (xldate, XL_CELL_DATE, XL_CELL_EMPTY, XL_CELL_TEXT,
                  XL_CELL_BLANK, XL_CELL_ERROR, XL_CELL_BOOLEAN, XL_CELL_NUMBER)
import xlrd

import numpy as np

from ._xlref import _Spreadsheet


log = logging.getLogger(__name__)

# noinspection PyUnresolvedReferences
# noinspection PyUnresolvedReferences
if LooseVersion(xlrd.__VERSION__) >= LooseVersion("0.9.3"):
    _xlrd_0_9_3 = True
else:
    _xlrd_0_9_3 = False


def _parse_cell(xcell, epoch1904=False):
    """
    Parse a xl-xcell.

    :param xlrd.Cell xcell: an excel xcell
    :type xcell: xlrd.sheet.Cell

    :param epoch1904:
        Which date system was in force when this file was last saved.
        False => 1900 system (the Excel for Windows default).
        True => 1904 system (the Excel for Macintosh default).
    :type epoch1904: bool

    :return: formatted xcell value
    :rtype:
        int, float, datetime.datetime, bool, None, str, datetime.time,
        float('nan')


    Examples::

        >>> import xlrd
        >>> from xlrd.sheet import Cell
        >>> _parse_cell(Cell(xlrd.XL_CELL_NUMBER, 1.2))
        1.2

        >>> _parse_cell(Cell(xlrd.XL_CELL_DATE, 1.2))
        datetime.datetime(1900, 1, 1, 4, 48)

        >>> _parse_cell(Cell(xlrd.XL_CELL_TEXT, 'hi'))
        'hi'
    """

    ctype = xcell.ctype

    if ctype == XL_CELL_NUMBER:
        # GH5394 - Excel 'numbers' are always floats
        # it's a minimal perf hit and less suprising
        val = int(xcell.value)
        if val == xcell.value:
            return val
        return xcell.value
    elif ctype in (XL_CELL_EMPTY, XL_CELL_BLANK):
        return None
    elif ctype == XL_CELL_TEXT:
        return xcell.value
    elif ctype == XL_CELL_BOOLEAN:
        return bool(xcell.value)
    elif ctype == XL_CELL_DATE:  # modified from Pandas library
        if _xlrd_0_9_3:
            # Use the newer xlrd datetime handling.
            d = xldate.xldate_as_datetime(xcell.value, epoch1904)

            # Excel doesn't distinguish between dates and time, so we treat
            # dates on the epoch as times only. Also, Excel supports 1900 and
            # 1904 epochs.
            epoch = (1904, 1, 1) if epoch1904 else (1899, 12, 31)
            if (d.timetuple())[0:3] == epoch:
                d = datetime.time(d.hour, d.minute, d.second, d.microsecond)
        else:
            # Use the xlrd <= 0.9.2 date handling.
            d = xldate.xldate_as_tuple(xcell.value, epoch1904)
            if d[0] < datetime.MINYEAR:  # time
                d = datetime.time(*d[3:])
            else:  # date
                d = datetime.datetime(*d)
        return d
    elif ctype == XL_CELL_ERROR:
        return float('nan')

    raise ValueError('invalid xcell type %s for %s' %
                     (xcell.ctype, xcell.value))


class XlrdSheet(_Spreadsheet):

    def __init__(self, sheet, epoch1904=False):
        if not isinstance(sheet, xlrd.sheet.Sheet):
            raise ValueError("Invalid xlrd-sheet({})".format(sheet))
        _Spreadsheet.__init__(self, sheet)
        self._epoch1904 = epoch1904

    def _read_states_matrix(self):
        """See super-method. """
        types = np.array(self._sheet._cell_types)
        return (types != XL_CELL_EMPTY) & (types != XL_CELL_BLANK)

    def read_rect(self, up_coords, dn_coords):
        """See super-method. """
        up_row, up_col = up_coords
        dn_row, dn_col = dn_coords
        sheet = self._sheet
        states_matrix = self.get_states_matrix()

        dn_row += 1  # inclusive
        dn_col += 1  # inclusive
        table = []
        for r in range(up_row, dn_row):
            row = []
            table.append(row)
            for c in range(up_col, dn_col):
                try:
                    if states_matrix[r, c]:
                        c = _parse_cell(sheet.cell(r, c), self._epoch1904)
                        row.append(c)
                        continue
                except IndexError:
                    pass
                row.append(None)

        return table
