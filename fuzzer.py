#!/usr/bin/env python3 -X utf8
from __future__ import print_function

import argparse
import json
import signal
import sys
import tempfile
from logging import _nameToLevel as levelNames

from kitty.interfaces import WebInterface
from kitty.model import GraphModel

from apifuzzer.fuzzer_target.fuzz_request_sender import FuzzerTarget
from apifuzzer.server_fuzzer import OpenApiServerFuzzer
from apifuzzer.swagger_template_generator import SwaggerTemplateGenerator
from apifuzzer.utils import set_logger, get_api_definition_from_file, save_api_definition


class Fuzzer(object):

    def __init__(self, api_resources, report_dir, test_level, log_level, basic_output, alternate_url=None,
                 test_result_dst=None,
                 auth_headers=None):
        self.api_resources = api_resources
        self.base_url = None
        self.alternate_url = alternate_url
        self.templates = None
        self.test_level = test_level
        self.report_dir = report_dir
        self.test_result_dst = test_result_dst
        self.auth_headers = auth_headers if auth_headers else {}
        self.logger = set_logger(log_level, basic_output)
        self.logger.info('APIFuzzer initialized')

    def prepare(self):
        # here we will be able to branch the template generator if we will support other than Swagger
        template_generator = SwaggerTemplateGenerator(self.api_resources, logger=self.logger)
        template_generator.process_api_resources()
        self.templates = template_generator.templates
        self.base_url = template_generator.compile_base_url(self.alternate_url)

    def run(self):
        target = FuzzerTarget(name='target', base_url=self.base_url, report_dir=self.report_dir,
                              auth_headers=self.auth_headers)
        interface = WebInterface()
        model = GraphModel()
        for template in self.templates:
            model.connect(template.compile_template())
        fuzzer = OpenApiServerFuzzer()
        fuzzer.set_model(model)
        fuzzer.set_target(target)
        fuzzer.set_interface(interface)
        fuzzer.start()


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1', 'True', 'T'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0', 'False', 'F'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


if __name__ == '__main__':

    def signal_handler(sig, frame):
        sys.exit(0)


    def json_data(arg_string):
        try:
            return json.loads(arg_string)
        except Exception as e:
            raise argparse.ArgumentError('{} is not JSON'.format(arg_string))


    parser = argparse.ArgumentParser(description='API fuzzer configuration',
                                     formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=20))
    parser.add_argument('-s', '--src_file',
                        type=str,
                        required=False,
                        help='API definition file path. Currently only JSON format is supported',
                        dest='src_file')
    parser.add_argument('--src_url',
                        type=str,
                        required=False,
                        help='API definition url. Currently only JSON format is supported',
                        dest='src_url')
    parser.add_argument('-r', '--report_dir',
                        type=str,
                        required=False,
                        help='Directory where error reports will be saved. Default is temporally generated directory',
                        dest='report_dir',
                        default=tempfile.mkdtemp())
    parser.add_argument('--level',
                        type=int,
                        required=False,
                        help='Test deepness: [1,2], higher is the deeper !!!Not implemented!!!',
                        dest='level',
                        default=1)
    parser.add_argument('-u', '--url',
                        type=str,
                        required=False,
                        help='Use CLI defined url instead compile the url from the API definition. Useful for testing',
                        dest='alternate_url',
                        default=None)
    parser.add_argument('-t', '--test_report',
                        type=str,
                        required=False,
                        help='JUnit test result xml save path !!!Not implemented!!!',
                        dest='test_result_dst',
                        default=None)
    parser.add_argument('--log',
                        type=str,
                        required=False,
                        help='Use different log level than the default WARNING',
                        dest='log_level',
                        default='warning',
                        choices=[level.lower() for level in levelNames if isinstance(level, str)])
    parser.add_argument('--basic_output',
                        type=str2bool,
                        required=False,
                        help='Use basic output for logging (useful if running in jenkins). Example --basic_output=True',
                        dest='basic_output',
                        default=False)
    parser.add_argument('--headers',
                        type=json_data,
                        required=False,
                        help='Http request headers added to all request. Example: \'[{"Authorization": "SuperSecret"}, '
                             '{"Auth2": "asd"}]\'',
                        dest='headers',
                        default=None)
    args = parser.parse_args()
    api_definition_json = dict()
    if args.src_file:
        api_definition_json = get_api_definition_from_file(args.src_file)
    elif args.src_url:
        api_definition_json = save_api_definition(args.src_url, tempfile.mktemp())
    else:
        argparse.ArgumentTypeError('No API definition source provided -s, --src_file or --src_url should be defined')
        exit()
    prog = Fuzzer(api_resources=api_definition_json,
                  report_dir=args.report_dir,
                  test_level=args.level,
                  alternate_url=args.alternate_url,
                  test_result_dst=args.test_result_dst,
                  log_level=args.log_level,
                  basic_output=args.basic_output,
                  auth_headers=args.headers
                  )
    prog.prepare()
    signal.signal(signal.SIGINT, signal_handler)
    prog.run()
