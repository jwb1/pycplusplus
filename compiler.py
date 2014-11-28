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

from __future__ import print_function
import os
import subprocess
import shlex

class cplusplus_error(Exception):
    def __init__(self, desc):
        self.desc = desc

    def __str__(self):
        return self.desc

# Each time a command line tool is invoked, an instance of this is returned with
# the process return code and stdout output captured.
class invoke_result:
    def __init__(self, return_val, stdout, stderr):
        self.return_val = return_val
        self.stdout = stdout
        self.stderr = stderr

# Each "build_" compiler method takes a list of source files. Before invoking
# the compiler, each source file is checked against it's coresponding object
# file to determine if it needs to be rebuilt. A "rebuild_record" records all of
# the details; the source file, the object file the compiler would build, and
# the .dep file, which is a list of the header files the source file depends on.
class rebuild_record:
    def __init__(self, source, obj, dep):
        self.source = source
        self.obj = obj
        self.dep = dep

# Each compiler object should expose the following methods publicly:
# "host" = the name of the platform the tool runs on (Windows/Linux)
# "target_family" = the name of the platform the tool targets (windows/posix)
# "target_proc" = the name of the target CPU architecture (x86/x64)
# "build_static_lib" = compile and link a static library (.lib/.a)
# "build_shared_lib" = compile and link a shared library (.dll/.so)
# "build_application" = compile and link a program (.exe)

# The derived compiler classes need to directly implement the "host",
# "target_family" and "target_proc" methods. They also must implement the
# following methods to support the rest of the library:
# "detect" = Called to ensure the compiler is able to run (check install paths, etc...)
# "object_details" = Information about the object code associated with a source file type.
# "get_lib_name" = Convert a library name to file name.
# "compile" = Compile source files in to object code.
# "link_static_lib" = Link object code in to a static library.
# "link_module" = Link object code in to a shared library or application.

class compiler:
    object_details_extension_index = 0
    object_details_need_deps = 1

    link_module_type_shared = 0
    link_module_type_application = 1

    def print_console(self, string):
        print(string)

    def print_log(self, string):
        if self.log_file:
            print(string, file=self.log_file)

    def print_both(self, string):
        self.print_console(string)
        self.print_log(string)

    def handle_error(self, error_string):
        self.print_both(error_string)
        raise cplusplus_error(error_string)

    def invoke(self, command_line):
        command_line_string = ' '.join(command_line)
        self.print_log(command_line_string)
        proc = subprocess.Popen(
            shlex.split(command_line_string),
            shell=False,
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
            )
        console_out = proc.communicate()
        return (invoke_result(proc.returncode, console_out[0], console_out[1]))

    def build_object_code(self, name, output_dir, config, source_list, include_list, define_list):
        object_code_dir = os.path.join(output_dir, name + '.intermediates', 'obj')
        if not os.path.exists(object_code_dir):
            os.makedirs(object_code_dir)

        dep_dir = os.path.join(output_dir, name + '.intermediates', 'dep')
        if not os.path.exists(dep_dir):
            os.makedirs(dep_dir)

        # Do a source file update time check to figure out if which source files, if any
        # have been updated since the last compile.
        rebuild_list = []
        for source in source_list:
            source_split = os.path.split(source)
            source_name_split = os.path.splitext(source_split[1])
            source_base_name = source_name_split[0]
            source_extension = source_name_split[1]

            object_details = self.object_details(source_extension)

            source_obj_file_name = source_base_name + object_details[compiler.object_details_extension_index]
            source_obj = os.path.join(object_code_dir, source_obj_file_name)

            source_dep_file_name = source_base_name + '.dep'
            source_dep = os.path.join(dep_dir, source_dep_file_name)

            rebuild = False
            if not os.path.exists(source_obj):
                rebuild = True
            else:
                obj_last_modified = os.path.getmtime(source_obj)
                if os.path.getmtime(source) >= obj_last_modified:
                    rebuild = True
                elif object_details[compiler.object_details_need_deps]:
                    if not os.path.exists(source_dep):
                        rebuild = True
                    else:
                        # Dep file: At this point, we know the source file exists, but is
                        # not out of date, and the dep file exists from a previous compile;
                        # it's still valid though, as the source file is not out of date.
                        with open(source_dep, 'r') as deps_file:
                            deps_list = []
                            deps_text = deps_file.read()
                            deps_list += deps_text.splitlines()
                            for dep in deps_list:
                                if os.path.getmtime(dep) >= obj_last_modified:
                                    rebuild = True
                                    break

            if rebuild:
                rebuild_list.append(rebuild_record(source, source_obj, source_dep))

        # Run the compiler.
        if len(rebuild_list) > 0:
            self.compile(name, config, output_dir, rebuild_list, include_list, define_list)
            return True
        else:
            self.print_log("No source files have been updated; skipping compilation")
            return False

    def check_for_link_update(self, link_path, libpath_list, lib_list):
        # Examine all of the object code and libraries that will be linked in order
        # to determine if a re-link is necessary.
        if (not os.path.isfile(link_path)) or (len(lib_list) == 0):
            return True
        else:
            link_last_modified = os.path.getmtime(link_path)
            lib_last_modified = None
            # Each library has to be located in the search paths.
            for lib in lib_list:
                lib_name = self.get_lib_name(lib)
                for path in libpath_list:
                    current_lib_path = os.path.join(path, lib_name)
                    if os.path.isfile(current_lib_path):
                        lib_last_modified = os.path.getmtime(current_lib_path)
                        break
                if lib_last_modified:
                    break
            if lib_last_modified:
                if lib_last_modified >= link_last_modified:
                    return True
                else:
                    return False
            else:
                self.handle_error("error: Could not stat library for time stamp check")

    def build_static_lib(self, name, output_dir, config, source_list, include_list, define_list):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        log_file_name = os.path.join(output_dir, name + '.log')
        with open(log_file_name, 'w+') as self.log_file:
            self.print_both("-- Building static library %s -- " % name)

            built_code = self.build_object_code(
                name,
                output_dir,
                config,
                source_list,
                include_list,
                define_list
                )
            self.link_static_lib(
                name,
                output_dir,
                config,
                built_code
                )
        self.log_file = None

    def build_shared_lib(self, name, output_dir, config, source_list, include_list, define_list, libpath_list, lib_list):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        log_file_name = os.path.join(output_dir, name + '.log')
        with open(log_file_name, 'w+') as self.log_file:
            self.print_both("-- Building shared library %s -- " % name)

            built_code = self.build_object_code(
                name,
                output_dir,
                config,
                source_list,
                include_list,
                define_list
                )
            self.link_module(
                name,
                output_dir,
                config,
                built_code,
                compiler.link_module_type_shared,
                libpath_list,
                lib_list
                )
        self.log_file = None

    def build_application(self, name, output_dir, config, source_list, include_list, define_list, libpath_list, lib_list):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        log_file_name = os.path.join(output_dir, name + '.log')
        with open(log_file_name, 'w+') as self.log_file:
            self.print_both("-- Building application %s -- " % name)

            built_code = self.build_object_code(
                name,
                output_dir,
                config,
                source_list,
                include_list,
                define_list
                )
            self.link_module(
                name,
                output_dir,
                config,
                built_code,
                compiler.link_module_type_application,
                libpath_list,
                lib_list
                )
        self.log_file = None
