#!/usr/bin/env python

import argparse
import os
import subprocess
import sys

SOURCE_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
VENDOR_DIR = os.path.join(SOURCE_ROOT, 'vendor')
PYYAML_LIB_DIR = os.path.join(VENDOR_DIR, 'pyyaml', 'lib')
sys.path.append(PYYAML_LIB_DIR)
import yaml  #pylint: disable=wrong-import-position,wrong-import-order


def parse_args():
  parser = argparse.ArgumentParser(description='Run Google Test binaries')

  parser.add_argument('-c', '--config', required=True,
                      help='path to a tests config')
  parser.add_argument('-t', '--tests-dir', required=True,
                      help='path to a directory with binaries to run')
  parser.add_argument('-o', '--output-dir', required=True,
                      help='path to a folder to save tests results')

  args = parser.parse_args()

  # Absolutize and check paths.
  # 'config' must exist and be a file.
  args.config = os.path.abspath(args.config)
  if not os.path.isfile(args.config):
    parser.error("file '{}' doesn't exist".format(args.config))

  # 'tests_dir' must exist and be a directory.
  args.tests_dir = os.path.abspath(args.tests_dir)
  if not os.path.isdir(args.tests_dir):
    parser.error("directory '{}' doesn't exist".format(args.tests_dir))

  # 'output_dir' must exist and be a directory.
  args.output_dir = os.path.abspath(args.output_dir)
  if not os.path.isdir(args.output_dir):
    parser.error("directory '{}' doesn't exist".format(args.output_dir))

  return args


def main():
  args = parse_args()

  tests_list = TestsList(args.config, args.tests_dir)
  return tests_list.run_all(args.output_dir)


class TestsList():
  def __init__(self, config_path, tests_dir):
    self.config_path = config_path
    self.tests_dir = tests_dir

    # A dict with binary names (e.g. 'base_unittests') as keys
    # and various test data as values of dict type.
    self.tests = self.__get_tests_list(config_path)

  def __len__(self):
    return len(self.tests)

  def run(self, binary_name, output_dir=None):
    if not binary_name in self.tests:
      raise Error("'{0}' not found in config '{1}'".format(
          binary_name, self.config_path))

    return self.__run(binary_name, output_dir)

  def run_all(self, output_dir=None):
    suite_returncode = 0

    for binary_name in self.tests:
      test_returncode = self.run(binary_name, output_dir)
      suite_returncode += test_returncode

    return suite_returncode

  def __get_tests_list(self, config_path):
    tests_list = {}
    config_data = TestsList.__get_config_data(config_path)

    for data_item in config_data['tests']:
      (binary_name, excluded_tests) = TestsList.__get_raw_test_info(data_item)
      test_meta = self.__create_test_meta(binary_name, excluded_tests)
      tests_list[binary_name] = test_meta

    return tests_list

  @staticmethod
  def __get_config_data(config_path):
    with open(config_path, 'r') as stream:
      return yaml.load(stream)

  @staticmethod
  def __expand_shorthand(data):
    """ Treat a string as {'string_value': None}."""

    if type(data) is dict:
      return data

    if isinstance(data, basestring):
      return {data: None}

    assert False, "unexpected shorthand type: {}".format(type(data))

  @staticmethod
  def __get_raw_test_info(data_item):
    data_item = TestsList.__expand_shorthand(data_item)

    binary_name = data_item.keys()[0]
    excluded_tests = None

    configs = data_item[binary_name]
    if configs is not None:
      # List of excluded tests.
      if 'to_fix' in configs:
        excluded_tests = configs['to_fix']

      # List of platforms to run the tests on.
      # TODO(alexeykuzmin): Respect the "platform" setting.

    return (binary_name, excluded_tests)

  def __create_test_meta(self, binary_name, excluded_tests):
      binary_path = os.path.join(self.tests_dir, binary_name)
      test_binary = TestBinary(binary_path)
      test_meta = {
        'binary': test_binary,
        'excluded_tests': excluded_tests,
      }
      return test_meta

  def __run(self, binary_name, output_dir):
    test_meta = self.tests[binary_name]
    test_binary = test_meta['binary']
    excluded_tests = test_meta['excluded_tests']

    output_file_path = TestsList.__get_output_path(binary_name, output_dir)

    return test_binary.run(excluded_tests=excluded_tests,
                           output_file_path=output_file_path)

  @staticmethod
  def __get_output_path(binary_name, output_dir=None):
    if output_dir is None:
      return None

    return os.path.join(output_dir, "results_{}.xml".format(binary_name))


class TestBinary():
  def __init__(self, binary_path):
    self.binary_path = binary_path

    # Is only used when writing to a file.
    self.output_format = 'xml'

  def run(self, excluded_tests=None, output_file_path=None):
    gtest_filter = ""
    if excluded_tests is not None and len(excluded_tests) > 0:
      excluded_tests_string = TestBinary.__format_excluded_tests(
          excluded_tests)
      gtest_filter = "--gtest_filter={}".format(excluded_tests_string)

    gtest_output = ""
    if output_file_path is not None:
      gtest_output = "--gtest_output={0}:{1}".format(self.output_format,
                                                     output_file_path)

    args = [self.binary_path, gtest_filter, gtest_output]

    # Suppress stdout if we're writing results to a file.
    stdout = None
    if output_file_path is not None:
      devnull = open(os.devnull, 'w')
      stdout = devnull

    returncode = subprocess.call(args, stdout=stdout)
    return returncode

  @staticmethod
  def __format_excluded_tests(excluded_tests):
    return "-" + ":".join(excluded_tests)


if __name__ == '__main__':
  sys.exit(main())
