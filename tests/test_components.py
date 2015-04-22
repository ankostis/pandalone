from collections import OrderedDict
import doctest
import json
from textwrap import dedent
import unittest

import six

import numpy.testing as npt
from pandalone.components import (
    Assembly, FuncComponent, Pstep, convert_df_as_pmods_tuples, _Pmod)
import pandalone.components
import pandas as pd


class TestDoctest(unittest.TestCase):

    def test_doctests(self):
        failure_count, test_count = doctest.testmod(
            pandalone.components,
            optionflags=doctest.NORMALIZE_WHITESPACE)  # | doctest.ELLIPSIS)
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEquals(failure_count, 0, (failure_count, test_count))


class Test_Pmod(unittest.TestCase):

    def test_Pmod_merge_name(self):
        pm1 = _Pmod(_name='pm1')
        pm2 = _Pmod(_name='pm2')
        pm = pm1.merge(pm2)
        self.assertEqual(pm._name, 'pm2')
        self.assertEqual(pm1._name, 'pm1')
        self.assertEqual(pm2._name, 'pm2')
        pm = pm2.merge(pm1)
        self.assertEqual(pm._name, 'pm1')
        self.assertEqual(pm1._name, 'pm1')
        self.assertEqual(pm2._name, 'pm2')

        pm1 = _Pmod()
        pm2 = _Pmod(_name='pm2')
        pm = pm1.merge(pm2)
        self.assertEqual(pm._name, 'pm2')
        self.assertEqual(pm1._name, None)
        self.assertEqual(pm2._name, 'pm2')
        pm = pm2.merge(pm1)
        self.assertEqual(pm._name, 'pm2')
        self.assertEqual(pm1._name, None)
        self.assertEqual(pm2._name, 'pm2')

    def test_Pmod_merge_name_recurse(self):
        pm1 = _Pmod(_name='pm1', _children={'a': _Pmod(_name='R1')})
        pm2 = _Pmod(_name='pm2', _children={'a': _Pmod(_name='R2')})
        pm = pm1.merge(pm2)
        self.assertEqual(pm._children['a']._name, 'R2')
        self.assertEqual(pm1._children['a']._name, 'R1')
        self.assertEqual(pm2._children['a']._name, 'R2')
        pm = pm2.merge(pm1)
        self.assertEqual(pm._children['a']._name, 'R1')
        self.assertEqual(pm1._children['a']._name, 'R1')
        self.assertEqual(pm2._children['a']._name, 'R2')

    def test_Pmod_merge_children(self):
        pm1 = _Pmod(
            _name='pm1', _children={'a': _Pmod(_name='A'), 'c': _Pmod(_name='C')})
        pm2 = _Pmod(
            _name='pm2', _children={'b': _Pmod(_name='B'), 'a': _Pmod(_name='AA')})
        pm = pm1.merge(pm2)
        self.assertEqual(sorted(pm._children.keys()), list('abc'))
        pm = pm2.merge(pm1)
        self.assertEqual(sorted(pm._children.keys()), list('abc'))

        pm1 = _Pmod(
            _children={'a': _Pmod(_name='A'), 'c': _Pmod(_name='C')})
        pm2 = _Pmod(
            _name='pm2', _children={'b': _Pmod(_name='B'), 'a': _Pmod(_name='AA')})
        pm = pm1.merge(pm2)
        self.assertEqual(sorted(pm._children.keys()), list('abc'))
        pm = pm2.merge(pm1)
        self.assertEqual(sorted(pm._children.keys()), list('abc'))
        print(pm)

    def test_Pmod_merge_regexps(self):
        pm1 = _Pmod(_name='pm1', _regexps=OrderedDict([
            ('a', _Pmod(_name='A')), ('c', _Pmod(_name='C'))]))
        pm2 = _Pmod(_name='pm2', _regexps=OrderedDict([
            ('b', _Pmod(_name='B')), ('a', _Pmod(_name='AA'))]))
        print(pm1.merge(pm2))

    def test_Pmod_merge_all(self):
        pm1 = _Pmod(_name='pm1')
        pm2 = _Pmod(_name='pm2')
        print(_Pmod.merge_all([pm1, pm2]))


class TestPmods(unittest.TestCase):

    def test_convert_df_empty(self):
        df_orig = pd.DataFrame([])

        df = df_orig.copy()
        pmods = convert_df_as_pmods_tuples(df)
        self.assertEqual(pmods, [])
        npt.assert_array_equal(df, df_orig)

        df = df_orig.copy()
        pmods = convert_df_as_pmods_tuples(df, col_from='A', col_to='B')
        self.assertEqual(pmods, [])
        npt.assert_array_equal(df, df_orig)

    def test_convert_df_no_colnames(self):
        df_orig = pd.DataFrame([['/a/b', '/A/B']])

        df = df_orig.copy()
        pmods = convert_df_as_pmods_tuples(df)
        self.assertEqual(tuple(pmods[0]), ('/a/b', '/A/B'))
        npt.assert_array_equal(df, df_orig)

        df = df_orig.copy()
        pmods = convert_df_as_pmods_tuples(df, col_from='A', col_to='B')
        self.assertEqual(tuple(pmods[0]), ('/a/b', '/A/B'))
        npt.assert_array_equal(df, df_orig)

#     def test_build_pmods_names_orderedDict(self):
#         pmods_tuples = [
#             ('/a', 'A1/A2'),
#             ('/a/b', 'B'),
#         ]
#         pmods = build_pmods_from_tuples(pmods_tuples)
#         self.assertIsInstance(pmods, dict)
#         self.assertIsInstance(pmods[_PMOD_CHILD], OrderedDict)
#
#     def test_build_pmods_regex_orderedDict(self):
#         pmods_tuples = [
#             ('/a*', 'A1/A2'),
#             ('/a/b?', 'B'),
#         ]
#         pmods = build_pmods_from_tuples(pmods_tuples)
#         self.assertIsInstance(pmods, dict)
#         self.assertIsInstance(pmods[_PMOD_REGEX], OrderedDict)
#         self.assertIsInstance(pmods[_PMOD_CHILD], OrderedDict)
#         self.assertIsInstance(pmods[_PMOD_CHILD]['a'], OrderedDict)


class TestPstep(unittest.TestCase):

    def test_equality(self):
        p = Pstep()
        self.assertEqual(str(p), '.')
        self.assertEqual(p, Pstep('.'))
        self.assertEquals(str(p['.']), str(p))

        n = 'foo'
        p = Pstep(n)
        self.assertEqual(str(p), n)
        self.assertEquals(p, Pstep(n))
        self.assertEquals(str(p.foo), str(p))

        n = '/foo'
        p = Pstep(n)
        self.assertEqual(str(p), n)
        self.assertEquals(p, Pstep(n))
        p['12']
        self.assertNotEquals(str(p), '12')

    def test_buildtree_valid_ops(self):
        p = Pstep()
        p.abc
        p.abc['def']
        p['abc'].defg
        p.n123
        p['321']
        p._some_hidden = 12
        exp = [
            './abc/def',
            './abc/defg',
            './321',
            './n123',
        ]
        self.assertListEqual(sorted(p._paths), sorted(exp))

    def test_buildtree_invalid_ops(self):

        p = Pstep()

        def f1(p):
            p.abc = 1

        def f2(p):
            p['a'] = 1

        def f3(p):
            p['a']['b'] = 1

        def f4(p):
            p['a'].c = 1

        def f5(p):
            p['_hid'] = 1

        for f in [f1, f2, f3, f4, f5]:
            p = Pstep()
            with self.assertRaises(AssertionError, msg=f):
                f(p),

    def PMODS(self):
        return {
            '.': 'root',
            '_child_': {
                'a': 'b',
                'abc': 'BAR',
                'for': 'sub/path',
                '_child_': {
                    'def': 'DEF',
                    '_child_': {
                        '123': '234'
                    },
                }
            }
        }

    def test_pmods(self):
        p = Pstep(pmods={'MISS': 'BOO'})
        self.assertEquals(p, '.', (p, p._paths))
        p = Pstep('foo', pmods={'MISS': 'BOO'})
        self.assertEquals(p, 'foo', (p, p._paths))

        p = Pstep(pmods={'.': 'bar'})
        p.a
        self.assertEquals(p, 'bar', (p, p._paths))

        p = Pstep('root', pmods={'root': 'bar'})
        p.a
        self.assertEquals(p, 'bar', (p, p._paths))

        p = Pstep(pmods={'_child_': {'a': 'b'}})
        self.assertEquals(p.a, 'b', (p, p._paths))

        p = Pstep(pmods=self.PMODS())
        p.a
        p.abc['def']['123']
        self.assertListEqual(
            sorted(p._paths),
            sorted(['root/b', 'root/BAR/DEF/234']),
            (p, p._paths))

    def test_pmods_lock_not_applying(self):
        p = Pstep('not dot', pmods=self.PMODS())
        p.nota

        pmods = self.PMODS()
        pmods.pop('.')
        p = Pstep(pmods=pmods)

    def test_pmods_lock_CAN_RELOCATE(self):
        pmods = self.PMODS()
        pmods['.'] = 'deep/root'
        p = Pstep(pmods=pmods)
        p._lock = Pstep.CAN_RELOCATE
        p['for']._lock = Pstep.CAN_RELOCATE

    def test_pmods_lock_CAN_RENAME(self):
        pmods = self.PMODS()
        pmods['.'] = 'deep/root'
        p = Pstep(pmods=pmods)
        with self.assertRaises(ValueError, msg=p._paths):
            p._lock = Pstep.CAN_RENAME

        p = Pstep(pmods=self.PMODS())
        with self.assertRaises(ValueError, msg=p._paths):
            p['for']._lock = Pstep.CAN_RENAME

    def test_pmods_lock_LOCKED(self):
        p = Pstep(pmods=self.PMODS())
        with self.assertRaises(ValueError, msg=p._paths):
            p._lock = Pstep.LOCKED

        pmods = self.PMODS()
        pmods['.'] = 'deep/root'
        with self.assertRaises(ValueError, msg=p._paths):
            p._lock = Pstep.LOCKED

        pmods = self.PMODS()
        pmods.pop('.')
        p = Pstep(pmods=pmods)
        with self.assertRaises(ValueError, msg=p._paths):
            p.abc._lock = Pstep.LOCKED

        pmods = self.PMODS()
        pmods.pop('.')
        p = Pstep(pmods=pmods)
        with self.assertRaises(ValueError, msg=p._paths):
            p['for']._lock = Pstep.LOCKED

    def test_assign(self):
        p1 = Pstep('root')

        def f1():
            p1.a = 1

        def f2():
            p1.a = p1

        def f3():
            p1.a = Pstep()

        self.assertRaises(AssertionError, f1)
        self.assertRaises(AssertionError, f2)
        self.assertRaises(AssertionError, f3)

    def test_indexing(self):
        m = {'a': 1, 'b': 2, 'c': {'cc': 33}}
        n = 'a'
        p = Pstep(n)
        self.assertEqual(m[p], m[n])
        self.assertEqual(m[p[n]], m[n])

    def test_idex_assigning(self):
        m = {'a': 1, 'b': 2, 'c': {'cc': 33}}
        n = 'a'
        p = Pstep(n)
        self.assertEqual(m[p], m[n])
        self.assertEqual(m[p[n]], m[n])

    def test_schema(self):
        json.dumps(Pstep())
        json.dumps({Pstep(): 1})

    def test_json(self):
        p = Pstep()
        p._schema.allOf = {}
        p._schema.type = 'list'
        p.a._schema.kws = {'minimum': 1}

    @unittest.skip('Unknwon why sets fail with Pstep!')
    def test_json_sets(self):
        json.dumps({Pstep(), Pstep()})


class TestComponents(unittest.TestCase):

    def test_assembly(self):
        def cfunc_f1(comp, value_tree):
            comp.pinp().A
            comp.pout().B

        def cfunc_f2(comp, value_tree):
            comp.pinp().B
            comp.pout().C
        ass = Assembly(FuncComponent(cfunc) for cfunc in [cfunc_f1, cfunc_f2])
        ass._build()
        self.assertEqual(list(ass._iter_validations()), [])
        self.assertEqual(ass._inp, ['f1/A', 'f2/B'])
        self.assertEqual(ass._out, ['f1/B', 'f2/C'])

        pmods = {'f1': '/root', 'f2': '/root'}
        ass._build(pmods)
        self.assertEqual(
            sorted(ass._inp + ass._out), ['/root/A', '/root/B', '/root/B', '/root/C'])