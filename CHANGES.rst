..    include:: <isonum.txt>

#######
Changes
#######

.. contents::


Known deficiencies
==================

.. _todos-list:

TODOs
-----
- XLeash
    - Core:
        - Syntax:
            - [ ] Notation for specifying the "last-sheet".
            - [ ] Extend RC-coords: ^-1, _[-6], .-4
                - [ ] Cell becomes 4-tuple.
            - [ ] Expand meander `@`?
        - filters:
            - [ ] Slices and Index args on 'numpy' and 'df' filters.
        - [ ] Xlrd-read with slices.
        - [x] Add API for returning sheet-names.
        - [ ] Use weak-refs for SheetsFactory (thanks Vinz)
    - Struct:
        - [x] Plugins for backends (& syntax?)
        - [x] Plugins for filters.
        - [ ] Plugins for syntax?
    - TCs
        - [ ] More TCs.
    - Backends:
        - [ ] Invert wrapping of impl-sheets --> attach attribute, to reuse them.
        - [ ] xlwings
        - [ ] Clipboard
        - [ ] openpyxl
        - [ ] google-drive sheets
    - [ ] Split own project
        - [ ] README
    - [ ] Check TODOs in code

Rejected TODOs:
---------------
- xleash:
    - Support cubic areas; pandas create dict-of-dfs from multiple sheets.
    - Use *ast* library for filters; cannot extract safely opts.
    - Build Lasso-structs trees on `recursive` filter for debugging; carefully
        crafted exception-messages is enough.


Changelog
=========

v0.5.0 (14-May-2020): Drop PY3.5 & OrderedDict, fix null-check np-arrays
------------------------------------------------------------------------
+ DROP PY3.5 for it has no ordered dictionaries

  + replace the use of OrderedDict with vanilla (PY3.6) dicts. 

+ FIX(pandel): treat np-arrays as booleans by checking their size, recommended
  in `numpy/numpy#9583 <https://github.com/numpy/numpy/issues/9583>`_, 
  to handle np.arrays's future boolean behavior (yet deprecated).


v0.4.0 (5-Apr-2020): Auto-default Pandel
----------------------------------------
- FEAT(PANDEL): support auto defaulting/removing `nulls` with jsonschema validation.
- FIX(pandel): up-to-date patches to jsonschema for traversing pandas
  (see `Julian/jsonschema#675 <https://github.com/Julian/jsonschema/pull/675>`_)
- FEAT(CI): drop Python-3.5, test evenly, including Python-3.8.
- FEAT(build, doc): + ``[all]`` pip-extras (identical to ``[dev]``); document available
  pip-extras in Quickstart section.
- enh(CI): Pytest-ize travis & appveyor scripts.
- enh(build): ignore folder when black-formatting, to eradicate delays when pre-commiting.
- fix(xleash.TC): up-to-date `pyeval` msg in a TC.
- enh(site): drop RTD mock hacks; fix `xlwings` intersphinx url.


v0.3.4 (28-July-2019): xleash for pandas 0.25+
----------------------------------------------
- fix xleash for pandas 0.25+ (19-July 2019).
- Pstep:

  - enh: rename cstor 2nd arg from ``_proto_or_pmod --> maps`` and allow
    to pass a sequence of 2-tuples to define mappings.
  - feat: accept multiple tags at once.


v0.3.3 (21-June-2019, UNRELEASED): jsonschema multi-dim numpy-arrays
--------------------------------------------------------------------
+ accept multi-dim numpy-arrays as jsonschema-arrays


v0.3.2 (19-June-2019, UNRELEASED): relax *asteval* lower-bound
--------------------------------------------------------------
- Support also asteval <0.9.10 (but still >0.9.7 needed for PY35+)


v0.2.8 (7-Sept-2019): BACKPORT fix for pandas 0.25+ (19-July 2019)
------------------------------------------------------------------
- Fix xleash for pandas 0.25+ (19-July 2019).
- Fix *asteval* *xleash* filter to work correctly with latest version
  using `usersym` table for context-variables (were missing those);
  relax *asteval* version lower-bound < 0.9.10, but bump dependency 
  from ``>= 0.9.7 --> 0.9.8``.
- Fix #13: ``ensure_filename()`` util were duping filename's file-extension
  if was given the same.
- Fix missing test-deps `ddt` & `openpyxl`.
- Fix git ignores.



v0.2.7 (15-July-2019): stray sources
------------------------------------
- fix: remove stray sources from xleash
  (`xleash.io._xlwings` has syntax-errors irritating linters)
- feat: backport build/bumpver scripts from v0.3.x
  (above bug was a results of a bad build).


v0.3.3 (21-June-2019): accept multi-dim numpy-arrays as jsonschema-arrays
-------------------------------------------------------------------------


v0.3.2 (19-June-2019): relax *asteval* lower-bound
--------------------------------------------------
- Support also asteval <0.9.10 (but still >0.9.7 needed for PY35+)


v0.3.1 (18-June-2019): DROP PY2 & bump jsonschema 2.x-->3.x
-----------------------------------------------------------
- Drop support for Python 2.7 & 3.4, `which covers 95% of 2018 Python-3 installations
  (84% of Pythons in total)
  <https://www.jetbrains.com/research/python-developers-survey-2018/#python-3-adoption>`_
- Use latest jsonschem(draft7) for ``PandelVisitor``, using *jsonschema* lib,
  bringing its lower-bound from 2.x.x --> 3.0.0.
- Fix *asteval* *xleash* filter to work correctly with latest version
  using `usersym` table for context-variables (were missing those).
- Fix #13: ``ensure_filename()`` util were duping filename's file-extension
  if was given the same.
- Build & dev-dependencies enhancements.
- Make all TCs to pass in both CIs for linux & Windows.
- Suport PyTest for launching tests - *nosetest* is still used in CIs,
  an includes coverage also.
- style: auto-format python files with |black|_  using |pre-commit|_.
- Drop bloated documentation sections about installation and
  cmdline-tools that never existed.
- Note: v0.3.0 were missing low-boundary on jsonschema >=3.

.. |black| replace:: *black* opinionated formatter
.. _black: https://black.readthedocs.io/
.. |pre-commit| replace:: *pre-commit* hooks framework
.. _pre-commit: https://pre-commit.com/


v0.2.6 (5-June-2019): deps cleanup
-----------------------------------
- build:
  - drop dep-tricks for older Pythons & correct old missconceptions.
  - drop never used `openpyxl` dep
  - drop `sphinx_rtd_theme` not-really-needed-these-days dep


v0.2.5 (29-May-2018)
--------------------
- Fix py36 "nested regex" warning on ``xleash._parse`` module.
- Pin ``jsonschema <3`` since `_types` has been dropped.
- Updates to `setup.py`, dependencies & build-scripts.
- VSCode files & dev plugins.


v0.2.4.post1 (23-Aug-2018)
--------------------------
Released just to move ``easygui`` dependency to (renamed from ``xlwings``-->)
`[excel]` extras, just for co2mpas summer release.

- ``v0.2.4.post1`` had unwanted WIPs.


v0.2.4 (21-Mar-2017)
---------------------------------------
- fix(xleash.io, #12): sheet margins failed with > 32bit num of rows/cols


v0.2.3 (25-Feb-2017)
---------------------------------------
- chore(travis): stop PY2 builds, reduce use of *future* lib
- fix(xleash, #10): numpy-warning raised bc diffing booleans


v0.2.2 (7-Feb-2017): "Telos" release
---------------------------------------
- pandas filter updates to `0.19.1`.
- `utils.ensure_file_ext()` accepts multiple extensions/regexes.


v0.2.1 (2-Dec-2016): "Stop" release
---------------------------------------
- remove unused features: doit, tkUI.
- travis-test on CONDA-->"standard" py; test also unde4r PY36-dev.


v0.2.0 (2-Nov-2016): "Really?" release
---------------------------------------
- xleash:
  - Plugins for backends and filters.
  - Packaging now supports 3 extras:
  
    - ``xlrd`` for the typical backend plugin,
    - ``xlwings`` for the new backend, excel-utils & tests,
    - ``pandas`` for filters plugins.

  - FIX & rename pandas-filter ``series --> sr`` - did not return a ``Lasso``.
  - Always convert xl-ref paths a "local" or "remote" urls to facilitate
    backends & use their `url.params` instead of filter `opts`.
  - Rename ``io._sheets --> io.backend``.

- xlutils, deps: Upgraded to ``xlwings-0.9.x`` released Aug/2/2016
  (see `migration guide <http://docs.xlwings.org/en/stable/migrate_to_0.9.html>`_)
  - Dropped util-functions (provided by now `xlwings`) or renamed:

    - ``xlutils.get_active_workbook()``
    - ``xlutils.get_workbook()``
    - ``tests._tutils.xw_Workbook() --> tests._tutils.xw_no_save_Workbook()``

- utils: Add more file/str functions from co2mpas-sampling
  (which/where, convpath, convert to/from came_case, publicize norm/abs paths)
- Unfortunately, Travis were down during the release (actually logs did not work),
  so TCs fail :-(


v0.1.13 (1-Nov-2016):
---------------------
- chore(deps): unpin OpenPyXL==1.8.6, openpyxl-444 & pandas-10125 have been fixed.
- fix(pandas): FIX pandas-v0.19+ dataframe-filter reading code


v0.1.12 (July-2016): "Stegh" release
-----------------------------------------
- xleash:

  - Make ``_parse_xlref_fragment()`` public (remove ``'_'`` from prefix).
  - #7: FIX ``"df"`` filter to read multi-index excel-tables
    that is supported since ``pandas-v0.16.x``.

- Add API for returning sheet-names: ``SheetsFactory.list_sheetnames()``
  and ``Sheet.list_sheetnames()``.
- Mark as "beta" in python trove-classifiers - del non-release opening note.


v0.1.11 (Apr-2016):
----------------------------------------
  - Fix regression on install-dependencies.


v0.1.10 (Apr-2016):
----------------------------------------
- xleash:

  - #6: Gracefully handle absolute-paths & file-URLs.
  - #8: Accept xlrefs with only sheets (without rect edges)s.
  - #9: always return [] on empty sheets.
  - **Known issues:** TCs related to asteval and pandas-multi-indexing fail
    and need investigation/fixing respectively.

- pandata: Add ``resolve_path()`` supporting also relative-paths.
- TravisCI: Run TCs also on *py3.5*, stop testing on *py3.3*.
- **Known issues:** Dev-dependencies required for installation (regression).


- v0.1.9 (Dec-2015):
    - pstep: Add ``pstep_from_df()`` utility.


- v0.1.8 (Sep-2015):

    - deps: Do not require flake8.

- v0.1.7 (Sep-2015):

    - deps: Do not enforce pandas/numpy version.

- v0.1.6 (Sep-2015):

    - xleash: Minor forgotten regression from previous fix context-sheet.
    - pstep: Make steps work as pandas-indexes.

- v0.1.5 (Sep-2015): properly fix context-sheet on `Ranger` anf `SheetsFactory`.

- v0.1.4 (Sep-2015): xleash fixes

    - xleash: Temporarily-Hacked for not closing sibling-sheets.
    - xleash: handle gracefully targeting-failures as *empty* captures.

- v0.1.3 (Sep-2015):

    - xleash: perl-quoting xlrefs to avoid being treated as python-comments.

- v0.1.1 (Sep-2015): **1st working release**

    - xleash:

        - FIX missing `xleash` package from wheel.
        - Renamed package `xlasso`--> `xleash` and  factor-out `_filters`
          module.
        - Added `py-eval` filter.
        - Accept xl-refs quoted by any char.

- v0.1.0 (Sep-2015): **XLasso BROKEN!**

    - Release in *pypi* broken, missing xlasso.
    - The `mappings` and `xlasso` packages are considered ready to be used.

- v0.0.11 (XX-May-2015)
- v0.0.1.dev1 (01-March-2015)

