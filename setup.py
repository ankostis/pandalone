#! python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""'Installation script for *pandalone*.


Install:
========
To install it, assuming you have download the sources,
do the usual::

    python setup.py install

Or get it directly from the PIP repository::

    pip install pandalone

Or get it directly from the github repository::

    pip install git+https://github.com/pandalone/pandalone.git
"""
# Got ideas for project-setup from many places, among others:
#    http://www.jeffknupp.com/blog/2013/08/16/open-sourcing-a-python-project-the-right-way/
#    http://python-packaging-user-guide.readthedocs.org/en/latest/current.html

import io
import os
import re
import sys

from setuptools import setup, find_packages


__commit__ = ""

# Fail early on ancient python-versions
#
py_ver = sys.version_info
if py_ver < (2, 7):
    exit("Sorry, Python2 >= 2.7 is supported!")
if py_ver >= (3,) and py_ver < (3, 3):
    exit("Sorry, Python3 >= 3.3 is supported!")

proj_name = "pandalone"
mydir = os.path.dirname(__file__)


# Version-trick to have version-info in a single place,
# taken from: http://stackoverflow.com/questions/2058802/how-can-i-get-the-version
##
def read_project_version():
    fglobals = {}
    with io.open(os.path.join(mydir, proj_name, "_version.py"), encoding="UTF-8") as fd:
        exec(fd.read(), fglobals)  # To read __version__
    return fglobals["__version__"]


def read_text_lines(fname):
    with io.open(os.path.join(mydir, fname)) as fd:
        return fd.readlines()


def yield_rst_only_markup(lines):
    """
    :param file_inp:     a `filename` or ``sys.stdin``?
    :param file_out:     a `filename` or ``sys.stdout`?`

    """
    substs = [
        # Selected Sphinx-only Roles.
        #
        (r":abbr:`([^`]+)`", r"\1"),
        (r":envvar:`([^`]+)`", r"``env[$\1]``"),
        (r":ref:`([^`]+)`", r"ref: *\1*"),
        (r":term:`([^`]+)`", r"**\1**"),
        (r":dfn:`([^`]+)`", r"**\1**"),
        (r":(samp|guilabel|menuselection|doc|file):`([^`]+)`", r"\1(`\2`)"),
        # Sphinx-only roles:
        #        :foo:`bar`   --> foo(``bar``)
        #        :a:foo:`bar` XXX afoo(``bar``)
        #
        # (r'(:(\w+))?:(\w+):`([^`]*)`', r'\2\3(``\4``)'),
        (r":(\w+):`([^`]*)`", r"\1(`\2`)"),
        # emphasis
        # literal
        # code
        # math
        # pep-reference
        # rfc-reference
        # strong
        # subscript, sub
        # superscript, sup
        # title-reference
        # Sphinx-only Directives.
        #
        (r"\.\. doctest", r"code-block"),
        (r"\.\. module", r"code-block"),
        (r"\.\. currentmodule::", r"currentmodule:"),
        (r"\.\. plot::", r".. plot:"),
        (r"\.\. seealso", r"info"),
        (r"\.\. glossary", r"rubric"),
        (r"\.\. figure::", r".. "),
        (r"\.\. image::", r".. "),
        (r"\.\. dispatcher", r"code-block"),
        # Other
        #
        (r"\|version\|", r"x.x.x"),
        (r"\|today\|", r"x.x.x"),
        (r"\.\. include:: AUTHORS", r"see: AUTHORS"),
    ]

    regex_subs = [(re.compile(regex, re.IGNORECASE), sub) for (regex, sub) in substs]

    def clean_line(line):
        try:
            for (regex, sub) in regex_subs:
                line = regex.sub(sub, line)
        except Exception as ex:
            print("ERROR: %s, (line(%s)" % (regex, sub))
            raise ex

        return line

    for line in lines:
        yield clean_line(line)


proj_ver = read_project_version()


readme_lines = read_text_lines("README.rst")
description = readme_lines[1].strip()  # or else...pypa/setuptools#1390
long_desc = "".join(yield_rst_only_markup(readme_lines))
# Trick from: http://peterdowns.com/posts/first-time-with-pypi.html
download_url = "https://github.com/%s/%s/tarball/v%s" % (proj_name, proj_name, proj_ver)

install_requires = [
    "future >= 0.15.0",
    "toolz",
    "jsonschema >=2.5, <3",  # 3+ dropped `validator._types`
    "numpy",
    'mock; python_version == "2.7"',
    'asteval >=0.9.8'       # has fixed newville/asteval#21 on recusrion-limit 
]
test_reqs = ["nose", "coverage", "coveralls", "docopt", "ddt", "openpyxl"]

pandas_reqs = [
    # For xleash pandas filter.
    "pandas"
]
excel_reqs = [
    "xlwings >= 0.9.2 ; sys_platform == 'win32'",
    # For excel-macros locked msg-box.
    "easygui != 0.98",
]
xlrd_reqs = ["xlrd"]
doc_reqs = ["sphinx>=1.2",]  # for comparisons
dev_reqs = (
    test_reqs
    + pandas_reqs
    + excel_reqs
    + xlrd_reqs
    + doc_reqs
    + [
        "wheel",
        "twine",
        "pylint",
        # for VSCode autoformatting
        "black",
        # for VSCode RST linting
        "doc8",
        "sphinx-autobuild",
    ]
)

setup(
    name=proj_name,
    version=proj_ver,
    description=description,
    long_description=long_desc,
    long_description_content_type="text/x-rst",
    author="Kostis Anagnostopoulos at European Commission (JRC)",
    author_email="ankostis@gmail.com",
    url="https://github.com/%s/%s" % (proj_name, proj_name),
    download_url=download_url,
    project_urls={
        "Documentation": "https://%s.readthedocs.io/" % proj_name,
        "Sources": "https://github.com/%s/%s" % (proj_name, proj_name),
        "Bug Tracker": "https://github.com/%s/%s/issues" % (proj_name, proj_name),
    },
    keywords=[
        "python",
        "utility",
        "library",
        "data",
        "tree",
        "processing",
        "calculation",
        "dependencies",
        "resolution",
        "scientific",
        "engineering",
        "pandas",
        "simulink",
    ],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: Implementation :: CPython",
        "Development Status :: 4 - Beta",
        "Natural Language :: English",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Manufacturing",
        "Environment :: Console",
        "License :: OSI Approved :: European Union Public Licence 1.1 (EUPL 1.1)",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
    ],
    packages=find_packages(exclude=["tests"]),
    # include_package_data = True,
    package_data={proj_name: ["excel/*.vba", "excel/*.ico", "icons/*"]},
    install_requires=install_requires,
    # build_requires=[
    #     # PEP426-field actually not used by `pip` them, hence
    #     # included in /requirements/developmnet.pip.
    #     'setuptools',
    #     'setuptools-git >= 0.3',  # Gather package-data from all files in git.
    #     'wheel',
    #     'collective.checkdocs',
    # ],
    # dev_requires=[
    #     # PEP426-field actually not used by `pip` them, hence
    #     # included in /requirements/developmnet.pip.
    #     'sphinx>=1.4',
    # ],
    tests_require=["ddt", "nose", "coverage", "coveralls", "pandas", "xlrd"],
    test_suite="nose.collector",
    extras_require={
        "test": test_reqs,
        "excel": excel_reqs,
        "pandas": pandas_reqs,
        "xlrd": xlrd_reqs,
        "dev": dev_reqs,
    },
    entry_points={
        "pandalone.xleash.plugins": [
            "xlrd_be = pandalone.xleash.io._xlrd:load_as_xleash_plugin [xlrd]",
            "pandas_filters = pandalone.xleash._pandas_filters:load_as_xleash_plugin [pandas]",
        ]
    },
    zip_safe=True,
    options={
        "build_sphinx": {"build_dir": "doc/_build"},
        "bdist_wheel": {"universal": True},
    },
    platforms=["any"],
    # TODO: check when `run_requires` works.
    # run_requires=[
    #     {
    #         "requires": ["pywin32 > 1.0", "xlwings", "easygui"],
    #         "environment": "sys_platform == 'win32' or sys_platform == 'darwin'"
    #     },
    # ],
    # metadata_version="2.0",
)
