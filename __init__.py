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

__version__ = '0.0.1'
__all__ = ['get_supported_compilers', 'get_compiler']

__author__ = 'Joshua Buckman <josh@buckman.me>'

import platform

from .visualcpp import visual_cpp_2008_x86
from .visualcpp import visual_cpp_2008_x64
from .visualcpp import visual_cpp_2010_x86
from .visualcpp import visual_cpp_2010_x64
from .visualcpp import visual_cpp_2013_x86
from .visualcpp import visual_cpp_2013_x64

from .gcc import mingw_x86
from .gcc import linux_gcc_x86
from .gcc import linux_gcc_x64

all_compiler_list = [
    visual_cpp_2008_x86(),
    visual_cpp_2008_x64(),
    visual_cpp_2010_x86(),
    visual_cpp_2010_x64(),
    visual_cpp_2013_x86(),
    visual_cpp_2013_x64(),
    mingw_x86(),
    linux_gcc_x86(),
    linux_gcc_x64()
    ]

def get_supported_compilers():
    host = platform.system()
    compiler_name_list = []
    for compiler in all_compiler_list:
        if host == compiler.host():
            compiler_name_list.append(compiler.__class__.__name__)
    return compiler_name_list

def get_compiler(compiler_name):
    host = platform.system()
    for compiler in all_compiler_list:
        if host == compiler.host() and \
           compiler.__class__.__name__ == compiler_name and \
           compiler.detect():
            return compiler
    return None
