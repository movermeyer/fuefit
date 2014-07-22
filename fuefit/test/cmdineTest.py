#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2013-2014 ankostis@gmail.com
#
# This file is part of fuefit.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
'''Check cmdline parsing and model building.

Created on Apr 17, 2014

@author: ankostis
'''
import unittest
from collections import OrderedDict
import functools
import argparse
import os
import io, sys


from ..main import (build_args_parser, validate_file_opts, parse_key_value_pair, parse_many_file_args,
    assemble_model, validate_model, FileSpec, main, distribute_model)
from ..model import (json_dumps, base_model)
from .redirect import redirected  # @UnresolvedImport


class TestFuncs(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)

        self._test_fnames = ('temp.csv', 'strange.ext')
        for tfn in self._test_fnames:
            if (not os.path.exists(tfn)):
                tf = open(tfn, "w")
                tf.close()

        _exit_code = None
        _exit_msg = None

        self._failColumnsMsg = 'Not a COLUMN_SPEC syntax'
        self._failColumns = ['', '(dd)', 'quant((bad units))', 'quant --> ((bad units))', 'quant (complex ( units ))',
                'quant (open units']
        self._goodColumns = ['quant', 'spaced quant', 'quant (units)', 'quant (spaced units)', 'Pnorm (kJ / sec)']

        self._failKVPairsMsg = 'Not a KEY=VALUE syntax'
        self._failKVPairs = ['no_value', 'spa ced', 'spaced key = key', '3number=val',
            '_']
        self._goodKVPairs = {'k=v':'v', 'key=value':'value', 'Num_3_key = 3 ':'3', '_key=hidden_key':'hidden_key',
            'k = spaced value ':'spaced value', 'miss_value=':'',
            'k+=123':123, 'k*=12.3':12.3, 'k?=1':True, 'k?=true':True, 'k?=False':False, 'k?=on':True,
            'k := 3':3, 'k := 3.14':3.14, 'k := ["a", 3.14]':['a', 3.14], 'k:={"a":3.14, "2":[1, "1"]}':{'a':3.14, '2':[1, "1"]},
            'k @= 3':3, 'k @= 3.14':3.14, 'k @= ["a", 3.14]':['a', 3.14], 'k@={\'a\':3.14, "2":[1, "1"]}':{'a':3.14, '2':[1, "1"]},
            'path/key += 0': 0, '/rootpath/+=1':1
        }

        self._failFormatsMsg = 'invalid choice:'
        self._failFormats = ['file_frmt=', 'file_frmt=BAD', 'file_frmt=CSV BAD']
        self._goodFormats = ['file_frmt=AUTO', 'file_frmt=CSV', 'file_frmt=XLS']


    def get_args_parser(self):
        def _exit(p, status=0, message=None):
            if message:
                self._exit_msg = message
            self._exit_code = status

#         def _error(p, message):
#             self._exit_msg = message
#             self._exit_code = 2
        parser = build_args_parser('test', 'x.x.x', 'DESC', 'EPILOG')
#         parser.exit = _exit
#         parser.error = _error

        return parser


    def check_exits(self, cmdline, exit_code):
        mystdout = io.StringIO()
        mystderr = io.StringIO()
        opts = None  # @UnusedVariable
        with redirected(stdout=mystdout, stderr=mystderr):
            with self.assertRaises(SystemExit) as cm:
                parser = self.get_args_parser()
                opts = parser.parse_args(cmdline)

            if (cm.exception.code != exit_code):
                d = OrderedDict({
                     'CMDLNE': cmdline,
                     'STDOUT': mystdout.getvalue(),
                     'STDERR': mystderr.getvalue(),
                     'OPTS': opts,
                 })
                raise AssertionError(d)
        return opts, mystdout, mystderr



    def check_ok(self, cmdline, **kw):
        import io

        mystdout = io.StringIO()
        mystderr = io.StringIO()
        opts = None  # @UnusedVariable
        with redirected(stdout=mystdout, stderr=mystderr, **kw):
            try:
                parser = self.get_args_parser()
                opts = parser.parse_args(cmdline)
            except SystemExit as ex:
                d = OrderedDict({
                     'EX': ex,
                     'CMDLNE': cmdline,
                     'STDOUT': mystdout.getvalue(),
                     'STDERR': mystderr.getvalue(),
                     'OPTS': opts,
                 })
                raise AssertionError(d)

        return opts, mystdout, mystderr


    def checkParseOpt_fail(self, cmdline, bads, badMsg, exit_code = 2):
        for opt in bads:
            (opts, mystdout, mystderr) = self.check_exits(cmdline.split() + [opt], exit_code)

            self.assertIsNone(opts)
            self.assertFalse(mystdout.getvalue(), mystdout.getvalue())
            self.assertTrue(mystderr.getvalue().splitlines()[-1].find(badMsg) > 0, mystderr.getvalue())

        ## Test multiple bads in 1 line
        self.check_exits(cmdline.split() + bads, exit_code)


    def checkParseOpt_good(self, cmdline, goods, testNArgs=True):
        for opt in goods:
            (opts, mystdout, mystderr) = self.check_ok(cmdline.split() + [opt])

            self.assertIsNotNone(opts)
            self.assertFalse(mystderr.getvalue(), mystderr.getvalue())
            self.assertFalse(mystdout.getvalue(), mystdout.getvalue())

        ## Test multiple goods in 1 line
        if testNArgs:
            self.check_ok(cmdline.split() + list(goods))


#     def test0(self):
#         main('-mfuel=diesel'.split())


    def testHelpMsg(self):

        cmdline = '--help'
        exit_code = 0

        (opts, mystdout, mystderr) = self.check_exits(cmdline.split(), exit_code)

        self.assertIsNone(opts)
        self.assertFalse(mystderr.getvalue(), mystderr.getvalue())
        ## On errors, help-msg is not printed.
        self.assertTrue(mystdout.getvalue().find('DESC') > 0, mystdout.getvalue())  # @UndefinedVariable


    def testModelOverrides_fail(self):
        self.checkParseOpt_fail('-I funcs_map -m', [''] + self._failKVPairs, self._failKVPairsMsg)
    def testModelOverrides_good(self):
        self.checkParseOpt_good('-I funcs_map -m', self._goodKVPairs.keys())

    def testColumnNames_fail(self):
        self.checkParseOpt_fail('-c', self._failColumns, self._failColumnsMsg)
    def testColumnNames_good(self):
        self.checkParseOpt_good('-I temp.csv -c', self._goodColumns)

    def testColumnRenames_fail(self):
        self.checkParseOpt_fail('-r', self._failColumns, self._failColumnsMsg)
    def testColumnRenames_good(self):
        self.checkParseOpt_good('-I funcs_map -r', self._goodColumns)


    def testKVPairs_fail(self):
        self._failKVPairs
        for opt in self._failKVPairs:
            with self.assertRaises(argparse.ArgumentTypeError, msg=opt):
                parse_key_value_pair(opt)
    def testKVPairs_good(self):
        self._goodKVPairs
        for (arg, val) in self._goodKVPairs.items():
            (_, v) = parse_key_value_pair(arg)
            self.assertEqual(v, val, arg)

    def testFileSpec_fail(self):
        test_fnames = self._test_fnames
        cases = [
            [['']],
            [['missing.file']],
            [[test_fnames[0], 'file_frmt=BAD']],
            [[test_fnames[0], 'model_path=rel_path']],
            [[test_fnames[0], '2_bad=key']],
            [[test_fnames[1]]], # missing file_frmt
        ]
        for many_file_args in cases:
            with self.assertRaises(argparse.ArgumentTypeError, msg=many_file_args):
                parse_many_file_args(many_file_args, 'r')
            with self.assertRaises(argparse.ArgumentTypeError, msg=many_file_args):
                parse_many_file_args(many_file_args, 'r')

        all_cases = functools.reduce(lambda x, y: x+y, cases)
        with self.assertRaises(argparse.ArgumentTypeError, msg=all_cases):
            parse_many_file_args(all_cases, 'r')
        with self.assertRaises(argparse.ArgumentTypeError, msg=all_cases):
            parse_many_file_args(all_cases, 'r')

    def testFileSpec_good(self):
        test_fnames = self._test_fnames
        cases = [
            (('r', 'w'), [[test_fnames[0]]]),
            (('r', 'w'), [[test_fnames[0], 'file_frmt=AUTO']]),
            (('r', 'w'), [[test_fnames[0], 'model_path=']]),
            (('r', 'w'), [[test_fnames[0], 'file_frmt=CSV', 'model_path=/gjhgj']]),
            (('r', 'w'), [[test_fnames[0], 'some=other', 'keys+=4', 'fun:=[1, {"a":2}]']]),
            (('r', 'w'), [[test_fnames[1], 'file_frmt=CSV']]),
            (('r', 'w'), [['+', ]]),

            (('r', 'w'), [['-', ]]),
            (('r', 'w'), [['+', ]]),
            (('r', 'w'), [['-', 'file_frmt=JSON']]),
            (('r', 'w'), [['+', 'file_frmt=JSON']]),
            (('r', 'w'), [['-', 'file_frmt=CSV', 'model_path=/gjhgj']]),
            (('r', 'w'), [['+', 'file_frmt=CSV', 'model_path=/gjhgj']]),
        ]
        for (open_modes, many_file_args) in cases:
            for open_mode in open_modes:
                res = parse_many_file_args(many_file_args, open_mode)

        argparse.ArgumentTypeError(parse_many_file_args, functools.reduce(lambda x, y: x+y, cases), 'r')


    def testNumOfFileOpts_fail(self):
        cases = [
               {'I':None, 'icolumns':[1,2], 'irenames':None},
               {'I':[1], 'icolumns':[1,2], 'irenames':None},
               {'I':[1,2], 'icolumns':[1,2,3], 'irenames':None},

               {'I':None, 'irenames':[1,2], 'icolumns':None},
               {'I':[1], 'irenames':[1,2], 'icolumns':None},
               {'I':[1,2, 3], 'irenames':[1,2], 'icolumns':None},

               {'I':None, 'irenames':[1,2], 'icolumns':[1,2]},
               {'I':None, 'irenames':[1,2], 'icolumns':[1]},
               {'I':[1], 'irenames':[1,2], 'icolumns':[1]},
               {'I':[1], 'irenames':[1,2], 'icolumns':[1,2,3]},
               {'I':[1,2], 'irenames':[1,2,3], 'icolumns':None},
               {'I':[1,2,3], 'irenames':[1,2], 'icolumns':[1,2,3,4]},
               {'I':[1,2,3], 'irenames':[1], 'icolumns':[1,2,3,4]},
       ]
        for opts in cases:
            opts = argparse.Namespace(**opts)
            with self.assertRaises(argparse.ArgumentTypeError, msg=opts):
                validate_file_opts(opts)

    def testNumOfFileOpts_good(self):
        cases = [
               {'I':[1], 'icolumns':[1], 'irenames':None},
               {'I':[1,2], 'icolumns':None, 'irenames':[1,2]},
               {'I':[1,2], 'icolumns':[1,2], 'irenames':[1,2]},
               {'I':[1,2], 'icolumns':[1,2], 'irenames':[1]},
               {'I':[1,2], 'icolumns':[1], 'irenames':[1]},
       ]
        for opts in cases:
            opts = argparse.Namespace(**opts)
            validate_file_opts(opts)

    def testSmoke_BuildModel_model_overrideParse_n_print(self):
        import pandas as pd

        fname = 'test_table.csv'
        opts = {'m':[[('fuel','diesel')]] }
        filespecs = [
            FileSpec(pd.read_csv, fname, open(fname, 'r'), 'CSV', '/engine_points', None, {})
        ]
        opts = argparse.Namespace(**opts)
        mdl = assemble_model(filespecs, opts.m)

        print(json_dumps(mdl))


    def testBuildModel_validate(self):
        import pandas as pd

        fname = 'test_table.csv'
        model_overrides = [[('fuel','diesel')]]
        filespecs = [
            FileSpec(pd.read_csv, fname, open(fname, 'r'), 'CSV', '/engine_points', None, {})
        ]
        mdl = assemble_model(filespecs, model_overrides)
        validate_model(mdl)


    def testWriteModelparts_emptyModel(self):
        mystdout = io.StringIO()
        mdl = {}
        filespecs = [
            FileSpec('write_csv', '<mystream>', mystdout, 'CSV', '', None, {})
        ]

        mystdout = io.StringIO()
        distribute_model(mdl, filespecs)
        self.assertEqual('', mystdout.getvalue(), mystdout.getvalue())

    def testWriteModelparts_baseModel(self):
        mystdout = io.StringIO()
        mdl = base_model()
        filespecs = [
            FileSpec('write_csv', '<mystream>', mystdout, 'CSV', '', None, {})
        ]
        distribute_model(mdl, filespecs)
        self.assertEqual(json_dumps(mdl), mystdout.getvalue(), mystdout.getvalue())

    def testWriteModelparts_alteredModel(self):
        mystdout = io.StringIO()
        mdl = base_model()
        k = 'test_key'
        v = 'TEST_value'
        mdl['engine'][k] = v
        filespecs = [
            FileSpec('write_csv', '<mystream>', mystdout, 'CSV', '', None, {})
        ]
        distribute_model(mdl, filespecs)
        self.assertTrue(mystdout.getvalue().find(k) > 0, mystdout.getvalue())
        self.assertTrue(mystdout.getvalue().find(v) > 0, mystdout.getvalue())

    #def testWriteModelparts_dataframe(self):


class TestMain(unittest.TestCase):
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.held, sys.stdout = sys.stdout, io.StringIO()
        os.chdir(os.path.dirname(os.path.realpath(__file__)))

    def test_run_main_stdout(self):
        main('''-I FuelFit.xlsx  sheetname+=0 header@=None names:=["rpm","p","fc"]
                -I engine.csv file_frmt=SERIES model_path=/engine header@=None
                -m /engine/fuel=petrol
                -O - model_path= -v -d'''.split())
        self.assertGreater(sys.stdout.getvalue().strip().find('rpm'), 0)

    def test_run_main_fileout(self):
        main('''-I FuelFit.xlsx  sheetname+=0 header@=None names:=["rpm","p","fc"]
                -I engine.csv file_frmt=SERIES model_path=/engine header@=None
                -m /engine/fuel=petrol
                -O ~t.csv model_path=/engine_points index?=false'''.split())
        with open('~t.csv', 'r') as fp:
            txt = fp.read()
        self.assertGreaterEqual(txt.strip().find('rpm'), 0)

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        self.held, sys.stdout = sys.stdout, self.held
        print(self.held.getvalue())

if __name__ == "__main__":
    unittest.main()