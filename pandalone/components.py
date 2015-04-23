#! python
#-*- coding: utf-8 -*-
#
# Copyright 2013-2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
Defines the building-blocks of a "model":

components and assemblies:
    See :class:`Component`, :class:`FuncComponent` and :class:`Assembly`

paths and path-mappings (pmods):
    See :func:`build_pmods_from_tuples`, :class:`Pstep`
"""

from __future__ import division, unicode_literals

from abc import ABCMeta, abstractmethod, abstractproperty
from collections import OrderedDict
from copy import copy
import re
from unittest.mock import MagicMock

import functools as ft
from pandalone.pandata import iter_jsonpointer_parts
import pandas as pd


__commit__ = ""


class _Pmod(object):

    """
    A path-step mapping, which along with its child-pmods, forms a pmods-hierarchy.

    - The :term:`pmods` denotes the hierarchy of all path-step mappings,
      that either *rename* or *relocate* path-steps.
    - The :term:`pmod` is the mapping of a single path-step.
    - A mapping always refers to the *final* path-step, like that::

        FROM_PATH       TO_PATH       RESULT_PATH
        ---------       -------       -----------
        /rename/path    foo       --> /rename/foo        ## renaming
        /relocate/path  foo/bar   --> /relocate/foo/bar  ## relocation
        /root           a/b/c     --> /a/b/c             ## Relocates all /root sub-paths.

    - It is possible to match fully on path-steps using regular-expressions,
      and then to use any captured-groups in the mapped value::

        (/all(.*)/path, foo)   + all_1/path --> /all_1/foo
                               + allXXX     --> /allXXX          ## no change
        (/all(.*)/path, foo\1) + all_1/path --> /all_1/foo_1

      If more than one regex match, they are merged in the order declared
      (the latest one overrides a previous one).
    - Any exact child-name matches are applied and merged after regexs.
    - Use :meth:`from_tuples()` to construct the pmods-hierarchy.
    - The pmods are used internally by class:`Pstep` to correspond
      the component-paths of their input & output onto the actual
      value-tree paths.

    :ivar str alias:           (optional) the mapped-name of the pstep for
                               this pmod
    :ivar dict _steps:         {original_name --> pmod}
    :ivar OrderedDict _regxs:  {regex_on_originals --> pmod}

    """

    __slots__ = ['alias', '_steps', '_regxs']

    def __init__(self, alias=None, _steps={}, _regxs={}):
        """
        Args passed only for testing, remember `_regxs` to be (k,v) tuple-list!

        .. Note:: Volatile arg-defaults (empty dicts) are knowingly used , 
            to preserve memory; should never append in them!

        """
        self.alias = alias
        self._steps = _steps
        if _regxs:
            self._regxs = OrderedDict(
                (re.compile(k), v) for k, v in _regxs)
        else:
            self._regxs = _regxs

    def _append_regx(self, regx, rpmod=None):
        if not self._regs:
            self._regs = OrderedDict()
        self._regs[regx] = rpmod

    @classmethod
    def from_tuples(cls, pmods_tuples):
        """
        Turns a list of 2-tuples into a *pmods* hierarchy.

        Each tuple defines the renaming-or-relocation of the *final* part
        of some component path onto another one into value-trees, such as::

            (rename/path, foo)           --> rename/foo
            (relocate/path, foo/bar)     --> relocate/foo/bar


        In case the the "from" path contains any of the `[].*()` chars,
        it is assumed to be a regular-expression::

            (all(.*)/path, foo)
            (some[\d+]/path, foo\1)


        :return: a root pmod
        :rtype: _Pmod


        Example::

            >>> pmods_tuples = [
            ...     ('/a', 'A1/A2'),
            ...     ('/a/b', 'B'),
            ... ]
            >>> pmods = build_pmods_from_tuples(pmods_tuples)
            >>> pmods
            >>> pmods[_PMOD_CHILD]
            {'a': {'_name_': 'A1/A2'},
            '_child_':
                [('b': {'_name_': 'B'})]}

            >>> pmods_tuples = [
            ...     ('/a*', 'A1/A2'),
            ...     ('/a/b[123]', 'B'),
            ... ]
            >>> pmods = build_pmods_from_tuples(pmods_tuples)
            >>> pmods[_PMOD_REGEX]
            OrderedDict([('a*': {'_name_': 'A1/A2'])

            >>> pmods[_PMOD_CHILD]
            {'a': {'_regex_':
                OrderedDict([('b[123]', {'_name_': 'B'})])}}

        """
        root = _Pmod()
        for f, t in pmods_tuples:
            ppmods = root
            srcstep = None
            for srcstep in iter_jsonpointer_parts(f):
                if any(set('[].*()') & set(srcstep)):
                    # wildard-pattern
                    try:
                        # if not ppmods._regxs:
                        child = ppmods[_PMOD_REGEX]
                    except KeyError:
                        ppmods[_PMOD_REGEX] = child = OrderedDict()
                    try:
                        child[srcstep]
                    except KeyError:
                        ppmods[_PMOD_REGEX] = child = OrderedDict(
                            {srcstep: None})

                else:
                    # regular step-name
                    try:
                        child = ppmods[_PMOD_CHILD]
                    except KeyError:
                        ppmods[_PMOD_CHILD] = child = {srcstep: None}
                ppmods = child
            if srcstep and t:
                ppmods[srcstep] = t

        return root

    def _override_dict(self, attr, other):
        """
        Override this pmod's dict-attr with other's, recursively.

        - It may "share" (crosslink) the dict and/or its child-pmods
          between the two pmod args (`self` and `other`).
        - No dict is modified (apart from self, which must have been cloned
          previously by :meth:`_Pmod._merge()`), to avoid side-effects
          in case they were "shared".
        - It preserves dict-ordering so that `other` order takes precedence
          (its elements are the last ones).

        :param str attr:     either "_steps" or "_regxs"
        :param _Pmod self:   contains the dict that would be overridden
        :param _Pmod other:  contains the dict with the overrides
        """

        opmods = getattr(other, attr)
        if opmods:
            spmods = getattr(self, attr)
            if spmods:
                # Like `dict.update()` but
                # with recursive _merge on common items,
                # and preserving order.
                #
                opairs = []
                for name, opmod in opmods.items():
                    spmod = spmods.get(name)
                    if spmod:
                        mpmod = spmod._merge(opmod)
                    else:
                        mpmod = opmod  # Share other-pmod.
                    opairs.append((name, mpmod))

                okeys = opmods.keys()
                spairs = [(name, spmod)  # Share self-pmod.
                          for name, spmod in spmods.items()
                          if name not in okeys]

                opmods = type(spmods)(spairs + opairs)

            # Share other dict if self hadn't its own.
            setattr(self, attr, opmods)

    def _merge(self, other):
        """
        Clone this and override its props with props from other-pmod, recursively.

        Although it does not modify this, the `other` or their children pmods,
        it may "share" (crosslink) them, so pmods MUST NOT be modified later.

        :param _Pmod other: contains the dicts with the overrides
        :return: the cloned merged pmod
        :rtype: _Pmod

        Examples:

        Look how `_steps` are merged::

            >>> pm1 = _Pmod(alias='pm1', _steps={
            ...     'a':_Pmod(alias='A'), 'c':_Pmod(alias='C')})
            >>> pm2 = _Pmod(alias='pm2', _steps={
            ...     'b':_Pmod(alias='B'), 'a':_Pmod(alias='AA')})
            >>> pm = pm1._merge(pm2)
            >>> sorted(pm._steps.keys())
            ['a', 'b', 'c']


        And here it is `_regxs` merging, which preserves order::

            >>> pm1 = _Pmod(alias='pm1',
            ...             _regxs=[('d', _Pmod(alias='D')),
            ...                      ('a', _Pmod(alias='A')),
            ...                      ('c', _Pmod(alias='C'))])
            >>> pm2 = _Pmod(alias='pm2',
            ...             _regxs=[('b', _Pmod(alias='BB')),
            ...                      ('a', _Pmod(alias='AA'))])

            >>> pm1._merge(pm2)
            pmod('pm2', OrderedDict([(re.compile('d'), pmod('D')),
                       (re.compile('c'), pmod('C')),
                       (re.compile('b'), pmod('BB')),
                       (re.compile('a'), pmod('AA'))]))

            >>> pm2._merge(pm1)
            pmod('pm1', OrderedDict([(re.compile('b'), pmod('BB')),
                        (re.compile('d'), pmod('D')),
                        (re.compile('a'), pmod('A')),
                        (re.compile('c'), pmod('C'))]))
        """
        self = copy(self)

        if other.alias:
            self.alias = other.alias
        if other._steps:
            self._override_dict('_steps', other)
        if other._regxs:
            self._override_dict('_regxs', other)

        return self

    def __getitem__(self, name):
        """
        Merges and returns the child pmod for matched regexps and direct-one.

        :param str name:    the child path-step name of the pmod to return
        :return:            the merged-child pmod or None
        :rtype:             _Pmod

        Example::

            >>> pm = _Pmod(
            ...     _steps={'a': _Pmod(alias='A')},
            ...     _regxs=[('a\w*', _Pmod(alias='AWord')),
            ...              ('a\d*', _Pmod(alias='ADigit')),
            ...    ])
            >>> pm['a']
            pmod('A')

            >>> pm['abc']
            pmod('AWord')

            >>> pm['a12']
            pmod('ADigit')

            >>> pm['BAD'] is None
            True


        Note that intentionally it does not support the `in` operator,
        to avoid needless merges::

            >>> 'BAD' in pm
            Traceback (most recent call last):
            TypeError: expected string or buffer


        And notice how children of regexps are merged together
        (the final sub-steps below are intentionally invalid as _Pmods)::

            >>> pm = _Pmod(
            ...     _steps={'a':
            ...        _Pmod(alias='A', _steps={1: 11})},
            ...     _regxs=[
            ...        ('a\w*', _Pmod(alias='AWord', _steps={2: 22})),
            ...        ('a\d*', _Pmod(alias='ADigit', _steps={3: 33})),
            ...    ])
            >>> sorted(pm['a']._steps)    ## All children and regexps match.
            [1, 2, 3]

            >>> pm['aa']._steps           ## Only 'a\w*' matches.
            {2: 22}

            >>> sorted(pm['a1']._steps )  ## Both regexps matches.
            [2, 3]

        So it is possible to say::

            >>> pm['a1'][2]
            22
            >>> pm['a1'][3]
            33
            >>> pm['a$'] is None
            True
        """
        pmods = [rpmod
                 for regex, rpmod
                 in self._regxs.items()
                 if regex.fullmatch(name)]
        cpmod = self._steps.get(name)
        if cpmod:
            pmods.append(cpmod)

        if pmods:
            return ft.reduce(_Pmod._merge, pmods)

    def __repr__(self):
        args = [repr(a)
                for a in [self.alias, self._steps, self._regxs]
                if a]

        args = ', '.join(args)
        return 'pmod({})'.format(args)


def convert_df_as_pmods_tuples(df_pmods, col_from='from', col_to='to'):
    """
    Turns a a dataframe with `col_from`, `col_to` columns into a list of 2-tuples.

    :return: a list of 2-tuples that can be fed into :func:`build_pmods_from_tuples`.
    :rtype: list

    Example::

        >>> pmods_tuples = [
        ...     ('/a', 'A1/A2'),
        ...     ('/a/b', 'B'),
        ... ]
        >>> df_pmods = pd.DataFrame(pmods_tuples)
        >>> res = convert_df_as_pmods_tuples(df_pmods)
        >>> res
        rec.array([('/a', 'A1/A2'), ('/a/b', 'B')],
              dtype=[('from', 'O'), ('to', 'O')])

        >>> df_pmods.columns = ['Rename from', 'Rename to']
        >>> df_pmods['extra columns'] = ['not', 'used']
        >>> res = convert_df_as_pmods_tuples(
        ...         df_pmods, col_from='Rename from', col_to='Rename to')
        >>> res
        rec.array([('/a', 'A1/A2'), ('/a/b', 'B')],
              dtype=[('Rename from', 'O'), ('Rename to', 'O')])
        """
    if df_pmods.empty:
        return []
    cols_df = set(df_pmods.columns)
    if col_from not in cols_df or col_to not in cols_df:
        if df_pmods.shape[1] != 2:
            cols_miss = cols_df - set([col_from, col_to])
            msg = "Missing pmods-columns%s, and shape%s is not just 2 columns!"
            raise ValueError(msg % (cols_miss, df_pmods.shape))
        else:
            df_pmods.columns = [col_from, col_to]
    df = df_pmods[[col_from, col_to]]

    return df.to_records(index=False)


_NONE = object()
"""Denotes non-existent json-schema attribute in :class:`JSchema`."""


class JSchema(object):

    """
    Facilitates the construction of json-schema-v4 nodes on :class:`PStep` code.

    It does just rudimentary args-name check.   Further validations
    should apply using a proper json-schema validator.

    :param type: if omitted, derived as 'object' if it has children
    :param kws:  for all the rest see http://json-schema.org/latest/json-schema-validation.html

    """
    type = _NONE,  # @ReservedAssignment
    items = _NONE,  # @ReservedAssignment
    required = _NONE,
    title = _NONE,
    description = _NONE,
    minimum = _NONE,
    exclusiveMinimum = _NONE,
    maximum = _NONE,
    exclusiveMaximum = _NONE,
    patternProperties = _NONE,
    pattern = _NONE,
    enum = _NONE,
    allOf = _NONE,
    oneOf = _NONE,
    anyOf = _NONE,

    def todict(self):
        return {k: v for k, v in vars(self).items() if v is not _NONE}


class Pstep(str):

    """
    Automagically-constructed *renamable* paths for accessing data-tree.

    The "magic" autocreates psteps as they referenced, making writting code
    that access data-tree paths, natural, while at the same time the "model"
    of those tree-data gets discovered.

    Each pstep keeps internaly the *name* of a data-tree step, which, when
    created through recursive referencing, coincedes with parent's branch
    leading to this step.  That name can be modified with :class:`_Pmod`
    so the same data-accessing code can consume differently-named data-trees.

    :param str pname:    this pstep's name (stored at super-str object)
    :ivar Pstep _csteps: the child-psteps
    :ivar dict _pmods:   path-modifications used to construct this and
                         relayed to children
    :ivar int _lock:     one of
                         - :const:`Pstep.CAN_RELOCATE`(default, reparenting allowed),
                         - :const:`Pstep.CAN_RENAME`,
                         - :const:`Pstep.LOCKED' (neither from the above).
    :ivar dict _schema:  jsonschema data.


    Usage:

    .. Warning::
        String's slicing operations do not work on this string-subclass!

    - Just by referencing (non_private) attributes, they are created.

    - It raises :exc:`AssertionError` if any non-pstep value gets assigned
      as dict-item or as non-private attribute (ie `_name` is indeed allowed).

    - Use :meth:`_paths()` to get all defined paths so far.

    - Construction::

        >>> Pstep()
        `.`
        >>> Pstep('a')
        `a`

    - Paths are created implicitely as they are referenced::

        >>> m = {'a': 1, 'abc': 2, 'cc': 33}
        >>> p = Pstep('a')
        >>> assert m[p] == 1
        >>> assert m[p.abc] == 2
        >>> assert m[p['321'].cc] == 33

        >>> sorted(p._paths)
        ['a/321/cc', 'a/abc']

    - Its is possible to define "path-renames" on construction::

        >>> pmods = {'root':'/deeper/ROOT',
        ...    '_child_': {'abc': 'ABC', '_child_': {'foo': 'BAR'}}}
        >>> p = Pstep('root', pmods=pmods)
        >>> p.abc.foo
        `BAR`
        >>> p._paths
        ['/deeper/ROOT/ABC/BAR']

    - but if exceptions are thrown if marked as "locked":


    - Assignments are allowed only to special attributes::

        >>> p.assignments = 'FAIL!'
        Traceback (most recent call last):
        AssertionError: Cannot assign 'FAIL!' to '/deeper/ROOT/assignments'!  Only other psteps allowed.

        >>> p._but_hidden = 'Ok'


    TODO: Use __slot__ on Pstep.
    """

    CAN_RELOCATE = 3
    CAN_RENAME = 1
    LOCKED = 0

    @staticmethod
    def lockstr(lock):
        if lock >= Pstep.CAN_RELOCATE:
            return 'CAN_RELOCATE'
        if Pstep.LOCKED <= lock < Pstep.CAN_RELOCATE:
            return 'LOCKED'
        return 'LOCKED'

    def __new__(cls, pname='.', pmods=None):
        orig = pname
        if pmods:
            pname = pmods.get(pname, pname)
        self = str.__new__(cls, pname)
        self._orig = orig

        self._csteps = {}
        self._pmods = pmods
        vars(self)['_lock'] = Pstep.CAN_RELOCATE

        return self

    def __missing__(self, cpname):
        try:
            cpname = self._pmods.get(cpname, cpname)
            pmods = self._pmods[_PMOD_CHILD]
        except:
            pmods = None
        child = Pstep(cpname, pmods=pmods)
        self._csteps[cpname] = child
        return child

    def __getitem__(self, cpname):
        child = self._csteps.get(cpname, None)
        return child or self.__missing__(cpname)

    def __setitem__(self, cpname, value):
        raise self._ex_invalid_assignment(cpname, value)

    def __getattr__(self, cpname):
        if cpname.startswith('_'):
            msg = "'%s' object has no attribute '%s'"
            raise AttributeError(msg % (self, cpname))
        return self.__missing__(cpname)

    def __setattr__(self, cpname, value):
        if cpname.startswith('_'):
            str.__setattr__(self, cpname, value)
        else:
            raise self._ex_invalid_assignment(cpname, value)

    def _ex_invalid_assignment(self, cpname, value):
        msg = "Cannot assign '%s' to '%s/%s'!  Only other psteps allowed."
        return AssertionError(msg % (value, self, cpname))

    def __repr__(self):
        return '`%s`' % self

    @property
    def _lock(self):
        """One of `CAN_RELOCATE`, `CAN_RENAME`, `LOCKED'

        :raise: ValueError when setting stricter lock-value on a renamed/relocated pstep
        """
        return vars(self)['_lock']

    @_lock.setter
    def _lock(self, lock):
        if self != self._orig:
            if lock < Pstep.CAN_RENAME or (lock < Pstep.CAN_RELOCATE and '/' in self):
                msg = "Cannot rename/relocate '%s'-->'%s' due to %s!"
                raise ValueError(msg % (self._orig, self, Pstep.lockstr(lock)))
        vars(self)['_lock'] = int(lock)

    @property
    def _paths(self):
        p = []
        self._paths_(p)
        return p

    def _paths_(self, paths, prefix=None):
        """:return: all child/steps constructed so far, in a list"""
        if prefix:
            prefix = '%s/%s' % (prefix, self)
        else:
            prefix = self
        if self._csteps:
            for _, v in self._csteps.items():
                v._paths_(paths, prefix)
        else:
            paths.append(prefix)

    @property
    def _schema(self):
        """Updates json-schema-v4 on this pstep (see :class:`JSchema`)."""

        # Lazy create it
        #    (clients should check before`_schema_exists()`)
        #
        jschema = vars(self).get('_schema')
        if jschema is None:
            jschema = JSchema()
            vars(self)['_schema'] = jschema
        return jschema

    def _schema_exists(self):
        """Always use this to avoid needless schema-instantiations."""
        return '_schema' in vars(self)


name_uniqueizer = None  # TODO: Handle clashes on component-names.


class Component(object, metaclass=ABCMeta):

    """
    Encapsulates a function and its its inputs/outputs dependencies.

    It should be callable, and when executed it may read/modify
    the data-tree given as its 1st input.

    An opportunity to fix the internal-state (i.e. inputs/output/name)
    is when the  :meth:`_build()` is invoked.

    :ivar list _name:    identifier
    :ivar list _inp:     list/of/paths required on the data-tree (must not overlap with `out`)
    :ivar list _out:     list/of/paths modified on the data-tree (must not overlap with `inp`)

    Mostly defined through *cfuncs*, which provide for defining a component
    with a single function with a special signature, see :class:`FuncComponent`.
    """

    def __init__(self, name):
        if name_uniqueizer:
            name = name_uniqueizer(name)
        self._name = name
        self._inp = None
        self._out = None

    @abstractmethod
    def __call__(self, *agrs, **kws):
        pass

    @abstractmethod
    def _build(self, pmods=None):
        """Invoked once before run-time and should apply `pmaps` when given."""
        pass

    def _iter_validations(self):
        """ Yields a msg for each failed validation rule.

        Invoke it after :meth:`_build()` component.
        """
        # TODO: Implement Component's validation.

        if False:
            yield
#         expected_attrs = ['name', 'inp', 'out']
#         for attr in expected_attrs:
#             if not hasattr(self, attr):
#                 yield "`%s` is unset!" % attr


class FuncComponent(Component):

    """
    Converts a "cfunc" into a component.

    A cfunc is a function that modifies the values-tree with this signature::

        cfunc_XXXX(comp, vtree)

    where:

    comp:
        the  :class:`FuncComponent` associated with the cfunc

    vtree:
        the part of the data-tree involving the values to be modified
        by the cfunc

    It works also as a utility to developers of a cfuncs, since it is passed
    as their 1st arg.

    The cfuncs may use :meth:`pinp` and :meth:`pout` when accessing
    its input and output data-tree values respectively.
    Note that accessing any of those attributes from outside of cfunc,
    would result in an error.

    If a cfunc access additional values with "fixed' paths, then it has to
    manually add those paths into the :attr:`_inp` and :attr:`_out`
    lists.


    Example:

    This would be a fully "relocatable" cfunc::

        >>> def cfunc_calc_foobar_rate(comp, value_tree):
        ...     pi = comp.pinp()
        ...     po = comp.pout()
        ...
        ...     df = value_tree.get(pi)
        ...
        ...     df[po.Acc] = df[pi.V] / df[pi.T]

    To get the unmodified component-paths, use::

        >>> comp = FuncComponent(cfunc_calc_foobar_rate)
        >>> comp._build()
        >>> assert list(comp._iter_validations()) == []
        >>> sorted(comp._inp + comp._out)
        ['calc_foobar_rate/Acc', 'calc_foobar_rate/T', 'calc_foobar_rate/V']

    To get the path-modified component-paths, use::

        >>> pmods = {'calc_foobar_rate': '/A/B', '_child_':{'foo': 'FOO'}}
        >>> comp._build(pmods)
        >>> sorted(comp._inp + comp._out)
        ['/A/B/Acc', '/A/B/T', '/A/B/V']

        >>> comp._build(pmods)
        >>> sorted(comp._inp + comp._out)
        ['/A/B/Acc', '/A/B/T', '/A/B/V']

    """

    def __init__(self, cfunc, name=None):
        self._cfunc = cfunc
        if name is None:
            name = cfunc.__name__
            prefix = 'cfunc_'
            if name.startswith(prefix):
                name = name[len(prefix):]
        Component.__init__(self, name=name)

        # The following are initialized in _build():
        # self._inp = None
        # self._out = None
        # self._pmods = None
        # self._pinp = None
        # self._pout = None

    def __call__(self, *args, **kws):
        self._cfunc(self, *args, **kws)

    def _fetch_all_paths(self, pstep):
        return pstep._paths if pstep else []

    def pinp(self, path=None):
        """The suggested :class:`Pstep` for cfunc to use to access inputs."""
        p = self._pinp
        if p is None:
            p = Pstep(path or self._name, pmods=self._pmods)
            self._pinp = p
        return p

    def pout(self, path=None):
        """The suggested :class:`Pstep` for cfunc to use to access outputs."""
        p = self._pout
        if p is None:
            p = Pstep(path or self._name, pmods=self._pmods)
            self._pout = p
        return p

    def _build(self, pmods=None):
        """Extracts inputs/outputs from cfunc. """
        vtree = MagicMock()
        self._inp = []
        self._out = []
        self._pinp = None
        self._pout = None
        self._pmods = pmods

        self._cfunc(self, vtree)

        self._inp.extend(self._fetch_all_paths(self._pinp))
        self._out.extend(self._fetch_all_paths(self._pout))


class Assembly(Component):  # TODO: Assembly inherit Component

    """
    Example:

        >>> def cfunc_f1(comp, value_tree):
        ...     comp.pinp().A
        ...     comp.pout().B
        >>> def cfunc_f2(comp, value_tree):
        ...     comp.pinp().B
        ...     comp.pout().C
        >>> ass = Assembly(FuncComponent(cfunc) for cfunc in [cfunc_f1, cfunc_f2])
        >>> ass._build()
        >>> assert list(ass._iter_validations()) == []
        >>> ass._inp
        ['f1/A', 'f2/B']
        >>> ass._out
        ['f1/B', 'f2/C']

        >>> pmods = {'f1':'/root', 'f2':'/root'}
        >>> ass._build(pmods)
        >>> sorted(ass._inp + ass._out)
        ['/root/A', '/root/B', '/root/B', '/root/C']

    """

    def __init__(self, components, name=None):
        Component.__init__(self, name=name or 'assembly')
        self._comps = list(components)

    def __call__(self, *args, **kws):
        pass  # TODO: Invoke Dispatcher with Assembly's child-components.

    def _build(self, pmods=None):
        inp = set()
        out = set()
        for c in self._comps:
            c._build(pmods)
            inp.update(c._inp)
            out.update(c._out)
        self._inp = sorted(inp)
        self._out = sorted(out)


if __name__ == '__main__':
    raise "Not runnable!"
