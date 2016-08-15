#! python
#-*- coding: utf-8 -*-
#
# Copyright 2013-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

from __future__ import division, unicode_literals

import os
import re
import sys

from future.moves.collections import Sequence  # @UnresolvedImport
from past.types import basestring

import future.moves.urllib.parse as up
import future.moves.urllib.request as ur
import os.path as osp


__commit__ = ""

# Python-2 compatibility
#
try:  # pragma: no cover
    FileNotFoundError
except NameError:  # pragma: no cover
    FileNotFoundError = IOError  # @ReservedAssignment
else:  # pragma: no cover
    FileNotFoundError = OSError  # @ReservedAssignment


def fullmatch_py2(regex, string, flags=0):
    # NOTE: re.match("(?:" + regex + r")\Z", string, flags=flags)
    m = re.match(regex, string, flags=flags)
    if m and m.span()[1] == len(string):
        return m
try:  # pragma: no cover
    from re import fullmatch  # @UnusedImport
except ImportError:  # pragma: no cover
    fullmatch = fullmatch_py2

##############
#  Utilities
#


def str2bool(v):
    """
    Utility for parsing cmd-line args.

    :param str v: any of (case insensitive): yes/no, true/false, on/off

    Example::

        >>> str2bool('ON') == str2bool('on') == str2bool('12') == True
        True

        >>> str2bool('') == str2bool('  ') == str2bool('0') == False
        True
        >>> str2bool('no') == str2bool('off') == str2bool('off') == False
        True

        >>> str2bool(0)
        Traceback (most recent call last):
        ValueError: Invalid str-boolean(0) due to: 'int' object has no attribute 'strip'
        >>> str2bool(None)
        Traceback (most recent call last):
        ValueError: Invalid str-boolean(None) due to: 'NoneType' object has no attribute 'strip'

    """
    try:
        vv = v.strip().lower()
        if (vv in ("yes", "true", "on")):
            return True
        if (vv in ("no", "false", "off", '0')):
            return False
        return bool(vv)
    except Exception as ex:
        msg = 'Invalid str-boolean(%s) due to: %s'
        raise ValueError(msg % (v, ex))


def obj2bool(v):
    """
    Utility for parsing anything to bool.

    :param v:
            any of (case insensitive): yes/no, true/false, on/off, `None`,
            or object, optionally with :meth:``__bool__``.

    Example::

        >>> obj2bool(None) == obj2bool('') == obj2bool(0) == False
        True
    """
    return bool(v) and str2bool(v)


def is_travis():  # pragma: no cover
    return 'TRAVIS' in os.environ


def as_list(o):
    if isinstance(o, Sequence) and not isinstance(o, basestring):
        o = list(o)
    else:
        o = [o]
    return o

_file_drive_regex = re.compile(r'^([a-z]):(/)?(.*)$', re.I)
_denormpath_regex = re.compile(r'[^/\\][/\\]$', re.I)
_unc_prefix = '\\\\?\\'


def _normpath(path):
    p = osp.normpath(path)
    if _denormpath_regex.search(path):
        p = p + '/'
    return p


def path2url(path):
    """
    Converts Windows-path to a local('file:') URL, or preserves remote URLs.

    - REL WITHOUT drive-letter     --> LOCAL ABS on CWD
    - REL WITH drive-letter        --> LOCAL ABS(!)
    - ABS WITHOUT drive-letter     --> LOCAL ABS (which drive??)
    - ABS WITH drive-letter        --> LOCAL ABS
    - remote REL/ABS WITH/WITHOUT drive-letter pass through.
    - local/remote ABS UNC-paths   --> LOCAL/REMOTE ABS

    :param str path: anything descrbed above

    Complexity because Bill Gates copied the methods of Methodios and Kyrilos.
    """
    if path:
        # Trim UNCs, urljoin() makes nonsense, pathname2url() just fails.
        if path.startswith(_unc_prefix):
            path = path[3:]

        # UNIXize resiliently and join with base-URL,
        # UNLESS it start with drive-letter (not to be assumed as schema).
        #
        path = path.replace('\\', '/')
        m = _file_drive_regex.match(path)
        if m:
            # Eliminate those pesky drive-relative paths...
            if not m.group(2):
                path = '%s:/%s' % (m.group(1), m.group(3))
            path = 'file:///%s' % up.quote(path)
        else:
            # Use CWD as  URL-base to make it absolute.
            #
            cwd = ur.pathname2url('%s/' % os.getcwd())
            baseurl = up.urljoin('file:', cwd)
            path = up.urljoin(baseurl, path)

        # Expand vars, conditionally on remote or local URL.
        #
        parts = up.urlsplit(path)
        p = osp.expandvars(parts.path)
        if parts.scheme == 'file':
            p = osp.expanduser(p)
        p = _normpath(p).replace('\\', '/')
        path = up.urlunsplit(parts._replace(path=p))

    return path


def url2path(url):
    parts = up.urlsplit(url)
    cwd = ur.url2pathname('%s/' % os.getcwd())


def generate_filenames(filename):
    f, e = os.path.splitext(filename)
    yield filename
    i = 1
    while True:
        yield '%s%i%s' % (f, i, e)
        i += 1


def make_unique_filename(fname, filegen=generate_filenames):
    fname_genor = generate_filenames(fname)
    fname = next(fname_genor)
    while os.path.exists(fname):
        fname = next(fname_genor)
    return fname


def ensure_file_ext(fname, ext):
    """
    :param str ext: extension with dot(.)

    >>> assert ensure_file_ext('foo', '.bar')     == 'foo.bar'
    >>> assert ensure_file_ext('foo.bar', '.bar') == 'foo.bar'
    >>> assert ensure_file_ext('foo.', '.bar')    == 'foo..bar'
    >>> assert ensure_file_ext('foo.', 'bar')    == 'foo.bar'

    """
    _, e = os.path.splitext(fname)
    if e != ext:
        return '%s%s' % (fname, ext)
    return fname


def open_file_with_os(fpath):  # pragma: no cover
    # From http://stackoverflow.com/questions/434597/open-document-with-default-application-in-python
    #     and http://www.dwheeler.com/essays/open-files-urls.html
    import subprocess
    try:
        os.startfile(fpath)  # @UndefinedVariable
    except AttributeError:
        if sys.platform.startswith('darwin'):
            subprocess.call(('open', fpath))
        elif os.name == 'posix':
            subprocess.call(('xdg-open', fpath))
    return


class LoggerWriter:
    """From http://plumberjack.blogspot.gr/2009/09/how-to-treat-logger-like-output-stream.html"""

    def __init__(self, logger, level):
        self.logger = logger
        self.level = level

    def write(self, msg):
        if msg:
            line_endings = ['\r\n', '\n\r', '\n']
            for le in line_endings:
                if msg.endswith(le):
                    msg = msg[:-len(le)]
            if msg:
                self.logger.log(self.level, msg)

    def flush(self):
        pass

if __name__ == '__main__':
    raise NotImplementedError
