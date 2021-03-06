#!/usr/bin/env python
# -*- coding: utf-8 -*
#
# Copyright 2020 Glenn Töws
#
# This file is part of the Coveron project
#
# The Coveron project is licensed under the LGPL-3.0 license

"""Package main for Coveron Instrumenter.
"""

import sys
import os
import subprocess
import colorama
import json
import gzip
colorama.init()
coveron_path = getattr(
    sys, '_MEIPASS', os.path.dirname(os.path.realpath(__file__)))
sys.path.append(coveron_path)

from Parser import ClangBridge, Parser
from CIDManager import CIDManager
from Configuration import SourceFile, Configuration
from ArgumentHandler import ArgumentHandler
from Instrumenter import Instrumenter
from DataTypes import *


def main():
    # load configuration
    config: Configuration = Configuration()

    # load arguments
    ArgumentHandler(config)

    # write title and config, if verbose
    if config.verbose:
        print_title()
        config.print_config()

    # check if the output folder exists. if not, create it
    if not os.path.exists(config.output_abs_path):
        try:
            os.makedirs(config.output_abs_path)
        except:
            print(colorama.Fore.RED +
                  "COVERON ERROR: output folder couldn't be created." +
                  colorama.Fore.RESET)

    # check for existence of Coveron runtime helper
    runtime_helper_source_path = os.path.join(coveron_path,
                                              "coveron_runtime_helper", "src",
                                              "coveron_helper.c")
    runtime_helper_header_path = os.path.join(coveron_path,
                                              "coveron_runtime_helper", "src",
                                              "coveron_helper.h")
    if not (os.path.isfile(runtime_helper_source_path) and
            os.path.isfile(runtime_helper_header_path)):
        print(colorama.Fore.RED +
              "COVERON ERROR: Runtime helper not found!" + colorama.Fore.RESET)
        exit(1)

    # store runtime helper header path inside config for later use in instrumentation
    config.runtime_helper_header_path = runtime_helper_header_path

    # instantiate clang bridge
    clang_bridge = ClangBridge()

    if config.verbose:
        print("Starting Instrumentation ...")

    # create new instrumentation process for every source file detected by ArgumentHandler
    for source_file in config.source_files:
        source_file: SourceFile

        if config.verbose:
            print("Instrumenting " + source_file.input_file + " ...")

        # load source code
        source_code: SourceCode = ""
        if os.path.isfile(source_file.input_file):
            with open(source_file.input_file, 'r') as source_file_ptr:
                try:
                    source_code = source_file_ptr.read()
                except:
                    raise(RuntimeError(
                        source_file.input_file + " can't be accessed!"))
        else:
            raise(RuntimeError(source_file.input_file + " not found!"))

        # create a cid_manager
        cid_manager = CIDManager(config, source_file, source_code)

        # check if the file was already instrumented (check existence of cid, check if source hash is equal)
        # if it was already instrumented, we're skipping instrumentation, if config allows
        if not config.force:
            if os.path.isfile(source_file.cid_file) and os.path.isfile(source_file.output_file):
                with open(source_file.cid_file, 'r') as cid_file_ptr:
                    try:
                        cid_data = json.load(cid_file_ptr)
                    except:
                        try:
                            with gzip.GzipFile(source_file.cid_file, 'r') as cid_comp_file_ptr:
                                cid_data = json.load(cid_comp_file_ptr)
                        except:
                            pass

                    if cid_data["source_code_hash"] == cid_manager.get_source_code_hash():
                        if config.verbose:
                            print("Using cached version for " +
                                  source_file.input_file)
                        continue

        # create a clang bridge and get a clang AST from the source file
        clang_tree = clang_bridge.clang_parse(
            source_file.input_file, config.clang_args)

        # create a parser instance, pass the clang AST. Start the parser
        parser = Parser(config, cid_manager, clang_tree, source_code)
        parser.start_parser()

        # write cid data
        cid_manager.write_cid_file()

        # create a instrumenter instance
        instrumenter = Instrumenter(
            config, cid_manager, source_file, source_code)

        # create the instrumented source code and write the instrumened source file
        instrumenter.start_instrumentation()
        instrumenter.write_output_file()

        # delete cid_manager, parser and instrumenter instances
        del cid_manager
        del parser
        del instrumenter
        continue

    # delete clang bridge after running through every file
    del clang_bridge

    if config.verbose:
        print("Invoking compiler ...")

    # call the compiler with the pass thru arguments, the new instrumented files and the link to the runtime_helper (as absolute path)
    command_string = " ".join([config.compiler_exec,
                               config.compiler_args,
                               ' '.join(
                                   source_file.output_file for source_file in config.source_files),
                               runtime_helper_source_path])
    compiler_returncode = subprocess.call(command_string, shell=True)

    if config.verbose:
        if compiler_returncode != 0:
            print(colorama.Fore.RED + "Compiler failed!" + colorama.Fore.RESET)
        else:
            print(colorama.Fore.GREEN +
                  "Compiler succeeded!" + colorama.Fore.RESET)
    return


def print_title():
    """Prints a Coveron title to the console"""
    print(colorama.Fore.CYAN + "Coveron Instrumenter" + colorama.Fore.RESET)
    print("======================")


if __name__ == "__main__":
    main()
