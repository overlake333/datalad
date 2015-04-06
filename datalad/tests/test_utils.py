# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Test testing utilities

"""

import os, shutil
from os.path import join as opj
from ..utils import rotree, rm_empties, ls_tree

from nose.tools import ok_, eq_, assert_false, assert_raises
from .utils import with_tempfile, traverse_for_content, with_tree, ok_startswith


@with_tempfile(mkdir=True)
def test_rotree(d):
    d2 = opj(d, 'd1', 'd2') # deep nested directory
    f = opj(d2, 'f1')
    os.makedirs(d2)
    with open(f, 'w') as f_:
        f_.write("LOAD")
    rotree(d)
    # we shouldn't be able to delete anything
    assert_raises(OSError, os.unlink, f)
    assert_raises(OSError, shutil.rmtree, d)
    # but file should still be accessible
    with open(f) as f_:
        eq_(f_.read(), "LOAD")
    # make it RW
    rotree(d, False)
    os.unlink(f)
    shutil.rmtree(d)

@with_tree([
    ('loaded.txt', 'abracadabra'),
    ('empty.txt', ''),
    ('d1', (
        ('loaded2.txt', '1 f load'),
        ('d2',
            (('empty', ''),
             )),
        )),
    ('d3', (
        ('empty', ''),
        ('d2',
            (('empty', ''),
             )),
        )),
    ('d4', (
        ('loaded3', 'load'),
        )),
    ])
def test_traverse_for_content(d):
    # shouldn't blow if just ran without any callables and say that there is some load
    ok_(traverse_for_content(d))
    # but should report empty for
    eq_(traverse_for_content(opj(d, 'd1', 'd2')), False)
    eq_(traverse_for_content(opj(d, 'd3')), False)
    # but not upstairs for d1 since of loaded2.txt
    ok_(traverse_for_content(opj(d, 'd1')))
    ok_(traverse_for_content(opj(d, 'd4')))

    #
    # Verify that it seems to be calling callbacks appropriately
    #
    def cb_dummy_noargs(d):
        ok_(d is not None)

    def cb_dummy_kwargs(d, empty_files=None, empty_dirs=None):
        ok_(d is not None)
        ok_(isinstance(empty_files, list))
        ok_(isinstance(empty_dirs, list))
        for f in empty_files:
            ok_startswith(f, 'empty')

    ok_(traverse_for_content(d,
                             do_all=cb_dummy_noargs,
                             do_none=cb_dummy_noargs,
                             do_any=cb_dummy_noargs))

    ok_(traverse_for_content(d,
                             do_all=cb_dummy_kwargs,
                             do_none=cb_dummy_kwargs,
                             do_any=cb_dummy_kwargs,
                             pass_files=True))

    # more thorough tests
    def cb_any(d_, empty_files=None, empty_dirs=None):
        ok_(d_ is not None)
        if d_ == d:
            eq_(empty_files, ['empty.txt'])
            eq_(empty_dirs, ['d3'])
        elif d_ == opj(d, 'd1'):
            # indeed we have empty d2 but loaded.txt
            eq_(empty_files, [])
            eq_(empty_dirs, ['d2'])
        else:
            raise ValueError("Must not be called for %d" % d_)

    def cb_all(d_, empty_files=None, empty_dirs=None):
        ok_(d_ is not None)
        if d_ == opj(d, 'd4'):
            eq_(empty_files, [])
            eq_(empty_dirs, [])
        else:
            raise ValueError("Must not be called for %s" % d_)

    def cb_none(d_, empty_files=None, empty_dirs=None):
        ok_(d_ is not None)
        if d_ in (opj(d, 'd1', 'd2'), opj(d, 'd3', 'd2')):
            eq_(empty_files, ['empty'])
            eq_(empty_dirs, [])
        elif d_ == opj(d, 'd3'):
            eq_(empty_files, ['empty'])
            eq_(empty_dirs, ['d2'])
        else:
            raise ValueError("Must not be called for %s" % d_)

    ok_(traverse_for_content(d,
                             do_all=cb_all,
                             do_none=cb_none,
                             do_any=cb_any,
                             pass_files=True))


    # And now let's do some desired action -- clean it up!
    ok_(traverse_for_content(d,
                             do_none=rm_empties,
                             do_any=rm_empties,
                             pass_files=True))
    # And check what is left
    eq_(ls_tree(d),
        ['d1', opj('d1', 'loaded2.txt'), 'd4', opj('d4', 'loaded3'), 'loaded.txt'])


@with_tree([
    ('empty.txt', ''),
    ('d1', (
        ('d2',
            (('empty', ''),
             )),
        )),
    ('d3', (
        ('empty', ''),
        ('d2',
            (('empty', ''),
             )),
        )),
    ('d4', (
        ('empty', ''),
        )),
    ])
def test_traverse_for_content_fully_empty(d):
    # And now let's do some desired action -- clean it up!
    ok_(not traverse_for_content(d,
                             do_none=rm_empties,
                             do_any=rm_empties,
                             pass_files=True))
    # And check that nothing is left behind
    eq_(ls_tree(d), [])
