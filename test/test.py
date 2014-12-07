#   Python C++ Compiler Invocation Library
#   Copyright 2012-2014 Joshua Buckman
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import sys
import os
import shutil

argv = sys.argv
script_dir = os.path.abspath(os.path.dirname(argv[0]))
module_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))
sys.path.append(module_dir)

from pycplusplus import get_supported_compilers
from pycplusplus import get_compiler

def main():
    # Gather preliminary info
    test_dir = os.path.abspath(os.path.join(script_dir, 'test.tmp'))
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)

    # Write out a test .cpp file
    test_source = os.path.abspath(os.path.join(test_dir, 'test.cpp'))
    with open(test_source, 'w') as test_source_file:
        test_source_file.write(
"""
#include <stdio.h>

void main()
{
    printf("Hello World!\\n");
}
"""
        )
    source_list = [ test_source ]
    lib_list = [ "kernel32" ]

    # Compile the test source with each compiler
    supported_compilers = get_supported_compilers()
    for compiler_name in supported_compilers:
        print("Trying compiler: " + compiler_name)
        c = get_compiler(compiler_name)
        if c:
            for config in ['debug', 'release', 'ship']:
                output_dir = os.path.abspath(os.path.join(test_dir, compiler_name, config))
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                c.build_application(
                    'test' + compiler_name + config,
                    output_dir,
                    config,
                    source_list,
                    [ ], # include_dir_list
                    [ ], # define_list
                    [ ], # libpath_list
                    lib_list
                    )
        else:
            print("Compiler not found")

    #shutil.rmtree(test_dir)

if __name__ == "__main__":
    main()
