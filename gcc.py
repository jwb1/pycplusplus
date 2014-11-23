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

import os
import copy
import re
from .cplusplus import compiler

class gcc(compiler):
    def compile(self, name, config, output_dir, rebuild_list, include_list, define_list):
        compile_flags = ['-c',                 # compile only. No link on gcc/g++ invoke
                         '-Werror',            # treat warnings as errors
                         '-Wall',              # turn all all warnings
                         '-Wno-long-long',
                         '-g']                 # Produce debug output
        compile_flags.extend(self.target_compile_flags())
        if config == 'debug':
            compile_flags.append('-O0')      # Generate best possible code for debugging
        else:
            compile_flags.append('-Ofast')   # Generate fast code, including fastest floats

        for define in define_list:
            compile_flags.append('-D' + define)

        for include_dir in include_list:
            compile_flags.append('-I' + self.prep_path(include_dir))

        for include_dir in self.builtin_include_list:
            compile_flags.append('-I' + self.prep_path(include_dir))

        did_pch = False
        for rebuild_record in rebuild_list:
            source_split = os.path.split(rebuild_record[compiler.rebuild_record_source_index])
            source_name_split = os.path.splitext(source_split[1])
            source_base_name = source_name_split[0]
            source_extension = source_name_split[1]

            if source_base_name.lower() == 'precomp':
                if did_pch:
                    self.handle_error("error: found multiple precompiled header source files")

                # Super-naive C++ parsing; assume the precompiled header source file includes
                # ONE file only.
                precomp_match = None
                with open(rebuild_record[compiler.rebuild_record_source_index], 'r') as precomp_file:
                    precomp_text = precomp_file.read()
                    precomp_match = re.search(r'#include\s*[<"](.*)[>"]', precomp_text)

                if not precomp_match:
                    self.handle_error("error: Can not parse precompiled header source file")

                precompiled_header = precomp_match.group(1)
                precompiled_header_split = os.path.split(precompiled_header)

                new_include_dir = os.path.join(output_dir, name + '.intermediates', 'gch')

                precompiled_output_dir = os.path.join(new_include_dir, name)
                if not os.path.exists(precompiled_output_dir):
                    os.makedirs(precompiled_output_dir)

                precompiled_binary = os.path.join(precompiled_output_dir, source_split[1] + '.gch')

                if source_extension == '.c':
                    invocation_flags = [self.prep_path(self.gcc),
                                        '-std=gnu89']         # C 90 with GNU extensions
                elif source_extension == '.cpp':
                    invocation_flags = [self.prep_path(self.gpp),
                                        '-std=gnu++0x']       # C++ x11 with GNU extensions
                invocation_flags.extend(compile_flags)
                invocation_flags.extend(['-o' + self.prep_path(precompiled_binary),
                                         '-MD -MF' + self.prep_path(rebuild_record[compiler.rebuild_record_dep_index] + '.temp'),
                                         self.prep_path(rebuild_record[compiler.rebuild_record_source_index])])

                # Run it
                self.print_both("building precompiled header")
                invoke_tuple = self.invoke(invocation_flags)
                if invoke_tuple[compiler.invoke_tuple_return_index] != 0:
                    self.handle_error(invoke_tuple[compiler.invoke_tuple_stdout_index])

                self.process_dep_file(rebuild_record[compiler.rebuild_record_dep_index])

                # A bit of a procedural hack; no o file is generated by the gcc precompiled header
                # but we still want the dependency checking. So touch a 0 byte o file.
                precomp_obj = open(rebuild_record[compiler.rebuild_record_obj_index], 'a')
                precomp_obj.close()

                # Do not compile the precompiled header source file again
                rebuild_list.remove(rebuild_record)
                compile_flags.append('-I' + self.prep_path(new_include_dir))
                did_pch = True

        for rebuild_record in rebuild_list:
            source_split = os.path.split(rebuild_record[compiler.rebuild_record_source_index])
            source_name_split = os.path.splitext(source_split[1])
            source_base_name = source_name_split[0]
            source_extension = source_name_split[1]

            if source_extension == '.c':
                invocation_flags = [self.prep_path(self.gcc),
                                    '-std=gnu89']         # C 90 with GNU extensions
            elif source_extension == '.cpp':
                invocation_flags = [self.prep_path(self.gpp),
                                    '-std=gnu++0x']       # C++ x11 with GNU extensions
            invocation_flags.extend(compile_flags)
            invocation_flags.extend(['-o' + self.prep_path(rebuild_record[compiler.rebuild_record_obj_index]),
                                     '-MD -MF' + self.prep_path(rebuild_record[compiler.rebuild_record_dep_index] + '.temp'),
                                     self.prep_path(rebuild_record[compiler.rebuild_record_source_index])])

            # Run it
            self.print_both("compiling %s" % source_split[1])
            invoke_tuple = self.invoke(invocation_flags)
            if invoke_tuple[compiler.invoke_tuple_return_index] != 0:
                self.handle_error(invoke_tuple[compiler.invoke_tuple_stdout_index])

            self.process_dep_file(rebuild_record[compiler.rebuild_record_dep_index])

    def process_dep_file(self, dep_path):
        dep_temp_list = []
        with open(dep_path + '.temp', 'r') as dep_temp_file:
            dep_temp_text = dep_temp_file.read()
            dep_temp_list = dep_temp_text.splitlines()
        os.remove(dep_path + '.temp')

        dep_temp_list = dep_temp_list[1:]
        # Parse out the dependent header file information. Remmove duplicates.
        headers = []
        unique_headers = set()
        for line in dep_temp_list:
            # There may be multiple headers on a single line, parse out the quote
            # delimted paths before the space delimted ones.
            headers_in_line = []
            line = line.strip(' \t\r\n\\')

            first_quote = line.find('"', 0)
            while first_quote != -1:
                last_found = line.find('"', first_quote)
                if last_found == -1:
                    self.handle_error("error: mismatch quotes when parsing header list")
                headers_in_line.append(line[first_quote:last_found])
                del line[first_quote:last_quote]
                first_quote = line.find('"', 0)

            headers_in_line.extend(line.split())

            for header in headers_in_line:
                if len(header) > 0:
                    abs_header = os.path.abspath(header)
                    if not abs_header in unique_headers:
                        unique_headers.add(abs_header)
                        headers.append(abs_header)

        with open(dep_path, 'w') as dep_file:
            dep_file.write('\n'.join(headers))

    def link_static_lib(self, name, output_dir, config, built_code):
        lib_name = self.get_lib_name(name)
        lib_path = os.path.join(output_dir, lib_name)

        if not built_code and os.path.isfile(lib_path):
            self.print_both("%s is up to date" % lib_name)
            return

        # r = replace existing or insert new file(s) into the archive
        # c = do not warn if the library had to be created
        # s = create an archive index (cf. ranlib)
        ar_flags = [self.prep_path(self.ar), '-rcs']

        ar_flags.append(self.prep_path(lib_path))

        object_code_dir = os.path.join(output_dir, name + '.intermediates', "obj")
        for root, dirs, files in os.walk(object_code_dir, topdown=True):
            for filename in files:
                full_path = os.path.join(root, filename)
                if os.path.getsize(full_path) > 0:
                    ar_flags.append(self.prep_path(full_path))

        self.print_both("linking %s" % lib_name)
        invoke_tuple = self.invoke(ar_flags)
        if invoke_tuple[compiler.invoke_tuple_return_index] != 0:
            self.handle_error(invoke_tuple[compiler.invoke_tuple_stdout_index])

    def link_module(self, name, output_dir, config, built_code, link_module_type, libpath_list, lib_list):
        link_name = self.get_link_name(name, link_module_type)
        link_path = os.path.join(output_dir, link_name)
        link_libpath_list = copy.copy(libpath_list)
        link_libpath_list.extend(self.builtin_libpath_list)

        if not built_code and not self.check_for_link_update(link_path, link_libpath_list, lib_list):
            self.print_both("%s is up to date" % link_name)
            return

        ld_flags = [self.prep_path(self.gpp)]
        ld_flags.extend(self.target_link_flags(link_module_type))

        for libpath_dir in link_libpath_list:
            ld_flags.append('-L' + self.prep_path(libpath_dir))

        # TODO: -Map mapfile write the map file

        ld_flags.append('-o ' + self.prep_path(link_path))

        object_code_dir = os.path.join(output_dir, name + '.intermediates', "obj")
        for root, dirs, files in os.walk(object_code_dir, topdown=True):
            for filename in files:
                full_path = os.path.join(root, filename)
                if os.path.getsize(full_path) > 0:
                    ld_flags.append(self.prep_path(full_path))

        for lib in lib_list:
            ld_flags.append('-l' + lib)

        self.print_both("linking %s" % link_name)
        invoke_tuple = self.invoke(ld_flags)
        if invoke_tuple[compiler.invoke_tuple_return_index] != 0:
            self.handle_error(invoke_tuple[compiler.invoke_tuple_stdout_index])

        # Now, generate a stripped version
        link_path_split = os.path.split(link_path)
        link_path_name_split = os.path.splitext(link_path_split[1])

        stripped_path = os.path.join(
            link_path_split[0],
            link_path_name_split[0] + '_stripped' + link_path_name_split[1]
            )
        strip_flags = [self.prep_path(self.strip),
                       '-o' + self.prep_path(stripped_path),
                       self.prep_path(link_path)
                      ]
        self.invoke(strip_flags)

    def get_lib_name(self, name):
        return 'lib' + name + '.a'

class mingw_x86(gcc):
    def host(self):
        return 'Windows'

    def target_family(self):
        return 'windows'

    def target_proc(self):
        return 'x86'

    def object_details(self, source_extension):
        if source_extension == '.cpp' or source_extension == '.c':
            return ('.o', True)
        elif source_extension == '.rc':
            return ('.o', False)
        else:
            self.handle_error("error: Invalid source extension %1" % source_extension)

    def prep_path(self, path):
        return '"' + path + '"'

    def detect(self):
        # Try to extract the MinGW directory from PATH; try a hard coded default otherwise.
        self.bin_path = None
        path_split = os.environ['PATH'].split(';')
        for path in path_split:
            if os.path.exists(os.path.join(path, 'mingw32-gcc.exe')):
                self.bin_path = path
                break
        if not self.bin_path:
            if os.path.exists('c:\mingw\bin\mingw32-gcc.exe'):
                self.bin_path = 'c:\mingw\bin'
            else:
                return False

        self.tool_dir = os.path.abspath(os.path.join(self.bin_path, os.pardir))
        self.builtin_include_list = [os.path.join(self.tool_dir, 'include')]
        self.builtin_libpath_list = [os.path.join(self.tool_dir, 'lib')]
        self.gcc = os.path.join(self.bin_path, 'mingw32-gcc.exe')
        self.gpp = os.path.join(self.bin_path, 'mingw32-g++.exe')
        self.windres = os.path.join(self.bin_path, 'windres.exe')
        self.ar = os.path.join(self.bin_path, 'ar.exe')
        self.strip = os.path.join(self.bin_path, 'strip.exe')
        return True

    def compile(self, name, config, output_dir, rebuild_list, include_list, define_list):
        # Windows RC files need to be compiled here because the gcc base class is shared
        # with classes that compile for other target families.
        windres_flags = ['"' + self.windres + '"']

        for define in define_list:
            windres_flags.append('-D' + define)

        for include_dir in include_list:
            windres_flags.append('-I"' + include_dir + '"')

        for include_dir in self.builtin_include_list:
            windres_flags.append('-I"' + include_dir + '"')

        did_rc = False
        for rebuild_record in rebuild_list:
            source_split = os.path.split(rebuild_record[compiler.rebuild_record_source_index])
            source_name_split = os.path.splitext(source_split[1])
            source_base_name = source_name_split[0]
            source_extension = source_name_split[1]

            if source_extension.lower() == '.rc':
                if did_rc:
                    self.handle_error("error: found multiple resource source files")

                invocation_flags = copy.copy(windres_flags)
                invocation_flags.extend(['-o "' + rebuild_record[compiler.rebuild_record_obj_index] + '"',
                                         '-i "' + rebuild_record[compiler.rebuild_record_source_index] + '"'])

                # Run it
                self.print_both("resource compile %s" % source_split[1])
                invoke_tuple = self.invoke(invocation_flags)
                if invoke_tuple[compiler.invoke_tuple_return_index] != 0:
                    self.handle_error(invoke_tuple[compiler.invoke_tuple_stdout_index])

                rebuild_list.remove(rebuild_record)
                did_rc = True

        gcc.compile(self, name, config, output_dir, rebuild_list, include_list, define_list)

    def get_link_name(self, name, link_module_type):
        if link_module_type == compiler.link_module_type_shared:
            return 'lib' + name + '.dll'
        elif link_module_type == compiler.link_module_type_application:
            return name + '.exe'
        else:
            self.handle_error("error: invalid module link type")

    def target_compile_flags(self):
        return ['-march=core2', '-msse2', '-msse3', '-mfpmath=sse',
                '-D__MSVCRT_VERSION__=0x0700']

    def target_link_flags(self, link_module_type):
        link_flags = ['-Wl,--dynamicbase',         # Enable ASLR
                      '-Wl,--nxcompat']            # Image is compatible with DEP
        if link_module_type == compiler.link_module_type_shared:
            link_flags.extend(['-shared',
                               '-Wl,--dll'])
                               # TODO: specify '--out-implib' if we want to mix/match compilers
        elif link_module_type == compiler.link_module_type_application:
            link_flags.extend(['-Wl,--subsystem=console'])
        else:
            self.handle_error("error: invalid module link type")
        return link_flags

class linux_gcc(gcc):
    def host(self):
        return 'Linux'

    def target_family(self):
        return 'posix'

    def target_proc(self):
        return 'x86'

    def object_details(self, source_extension):
        if source_extension == '.cpp' or source_extension == '.c':
            return ('.o', True)
        else:
            self.handle_error("error: Invalid source extension %1" % source_extension)

    def prep_path(self, path):
        return path

    def detect(self):
        # Try to extract the GCC directory from PATH. We might not need this.
        self.bin_path = None
        path_split = os.environ['PATH'].split(':')
        for path in path_split:
            if os.path.exists(os.path.join(path, 'gcc')):
                self.bin_path = path
                break
        if not self.bin_path:
            return False

        # self.tool_dir is not needed or set for linux gcc.
        self.builtin_include_list = []
        self.builtin_libpath_list = []
        self.gcc = os.path.join(self.bin_path, 'gcc')
        self.gpp = os.path.join(self.bin_path, 'g++')
        self.ar = os.path.join(self.bin_path, 'ar')
        self.strip = os.path.join(self.bin_path, 'strip')
        return True

    def get_link_name(self, name, link_module_type):
        if link_module_type == compiler.link_module_type_shared:
            return 'lib' + name + '.so'
        elif link_module_type == compiler.link_module_type_application:
            return name
        else:
            self.handle_error("error: invalid module link type")

class linux_gcc_x86(linux_gcc):
    def target_compile_flags(self):
        return ['-m32', '-march=core2', '-msse2', '-msse3', '-mfpmath=sse', '-fpic']

    def target_link_flags(self, link_module_type):
        link_flags = ['-m32']
        if link_module_type == compiler.link_module_type_shared:
            link_flags.extend(['-shared'])
        elif link_module_type == compiler.link_module_type_application:
            pass
        else:
            self.handle_error("error: invalid module link type")
        return link_flags

class linux_gcc_x64(linux_gcc):
    def target_compile_flags(self):
        # TODO: Instruction set/tuning flags here
        return ['-m64 -mtune=generic', '-msse2', '-msse3', '-mfpmath=sse', '-fpic']

    def target_link_flags(self, link_module_type):
        link_flags = ['-m64']
        if link_module_type == compiler.link_module_type_shared:
            link_flags.extend(['-shared'])
        elif link_module_type == compiler.link_module_type_application:
            pass
        else:
            self.handle_error("error: invalid module link type")
        return link_flags