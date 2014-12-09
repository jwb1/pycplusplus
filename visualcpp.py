#   Python C++ Compiler Invocation Library
#   Copyright 2014 Joshua Buckman
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
from .compiler import compiler

class visual_cpp(compiler):
    split_includes_text_index = 0
    split_includes_deps_index = 1

    def host(self):
        return 'Windows'

    def target_family(self):
        return 'windows'

    def object_details(self, source_extension):
        if source_extension == '.cpp' or source_extension == '.c':
            return ('.obj', True)
        elif source_extension == '.rc':
            return ('.res', False)
        else:
            self.handle_error("error: Invalid source extension %1" % source_extension)

    def check_for_winsdk_in_key(self, winreg, key):
        # All of the Windows SDKs installed on the machine get their own sub-key here.
        done_key_enum = False
        version_keys = []

        key_info = winreg.QueryInfoKey(key)
        for index in range(key_info[0]):
            version_key = winreg.EnumKey(key, index)
            version_keys.append(version_key)

        # Select the version: The most recent v7.x SDK.
        selected_version = 0
        # TODO

        version_key = winreg.OpenKey(key, version_keys[selected_version])
        return winreg.QueryValueEx(version_key, 'InstallationFolder')[0]

    def find_winsdk(self):
        # Try to locate the Windows SDK. This is a heuristic, at best.
        winreg = __import__('_winreg')
        self.winsdk_dir = None

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'SOFTWARE\Microsoft\Windows Kits\Installed Roots')
            try:
                self.winsdk_dir = winreg.QueryValueEx(key, 'KitsRoot81')[0]
                self.winsdk_new_layout = True
            except:
                pass
            if not self.winsdk_dir:
                self.winsdk_dir = winreg.QueryValueEx(key, 'KitsRoot')[0]
                self.winsdk_new_layout = True
        except:
            pass

        if not self.winsdk_dir:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows Kits\Installed Roots')
                try:
                    self.winsdk_dir = winreg.QueryValueEx(key, 'KitsRoot81')[0]
                    self.winsdk_new_layout = True
                except:
                    pass
                if not self.winsdk_dir:
                    self.winsdk_dir = winreg.QueryValueEx(key, 'KitsRoot')[0]
                    self.winsdk_new_layout = True
            except:
                pass

        if not self.winsdk_dir:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'SOFTWARE\Microsoft\Microsoft SDKs\Windows')
                self.winsdk_dir = self.check_for_winsdk_in_key(winreg, key)
                self.winsdk_new_layout = False
            except:
                pass

        if not self.winsdk_dir:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Microsoft SDKs\Windows')
                self.winsdk_dir = self.check_for_winsdk_in_key(winreg, key)
                self.winsdk_new_layout = False
            except:
                pass

    def detect(self):
        vs_common_tools_var = self.get_vs_common_tools_var()
        if not vs_common_tools_var in os.environ:
            self.print_console("error: Visual C++ can not be located ({0} is not set.)".format(vs_common_tools_var))
            return False

        vs_common_tools = os.environ[vs_common_tools_var]
        if not os.path.isdir(vs_common_tools):
            self.print_console("error: Visual C++ can not be located ({0} is not valid.)".format(vs_common_tools_var))
            return False

        self.tool_dir = os.path.abspath(os.path.join(vs_common_tools, os.pardir, os.pardir, 'VC'))
        if not os.path.isdir(self.tool_dir):
            self.print_console("error: Visual C++ can not be located (VC directory not found.)")
            return False

        self.builtin_include_list = []
        self.builtin_libpath_list = []

        # Add Windows SDK stuff.
        self.find_winsdk()
        if not self.winsdk_dir or not os.path.isdir(self.winsdk_dir):
            self.print_console("error: Windows SDK can not be located.")
            return False

        # Find the MFC/ATL directory, if it's there.
        mfcatl_dir = os.path.join(self.tool_dir, 'atlmfc')
        if os.path.isdir(mfcatl_dir):
            self.mfcatl_dir = mfcatl_dir

        # Make sure to remove the magic environment variable to allow compiler
        # output to be redirected even from within the IDE.
        if 'VS_UNICODE_OUTPUT' in os.environ:
            del(os.environ['VS_UNICODE_OUTPUT'])

        return True

    def default_x86_tools(self):
        self.cl   = os.path.join(self.tool_dir, 'bin', 'cl.exe')
        self.link = os.path.join(self.tool_dir, 'bin', 'link.exe')
        self.lib  = os.path.join(self.tool_dir, 'bin', 'lib.exe')

        if self.mfcatl_dir:
            self.builtin_include_list.append(os.path.join(self.mfcatl_dir, 'include'))
            self.builtin_libpath_list.append(os.path.join(self.mfcatl_dir, 'lib'))

        if self.winsdk_new_layout:
            # Windows 8 and newer SDKs
            self.rc = os.path.join(self.winsdk_dir, 'bin', 'x86', 'rc.exe')
            self.builtin_include_list.append(os.path.join(self.winsdk_dir, 'Include', 'shared'))
            self.builtin_include_list.append(os.path.join(self.winsdk_dir, 'Include', 'um'))
            self.builtin_libpath_list.append(os.path.join(self.winsdk_dir, 'Lib', 'winv6.3', 'um', 'x86'))
        else:
            # Windows 7 and older SDKs
            self.rc = os.path.join(self.winsdk_dir, 'bin', 'rc.exe')
            self.builtin_include_list.append(os.path.join(self.winsdk_dir, 'include'))
            self.builtin_libpath_list.append(os.path.join(self.winsdk_dir, 'lib'))

        # Add the C standard library
        self.builtin_include_list.append(os.path.join(self.tool_dir, 'include'))
        self.builtin_libpath_list.append(os.path.join(self.tool_dir, 'lib'))

        # Visual C++ needs to access dlls scattered through the installation, so add to the PATH.
        path = os.environ['PATH']
        if path[-1] != ';':
            path += ';'
        path += os.path.abspath(os.path.join(self.tool_dir, os.pardir, 'Common7', 'IDE'))
        path += ';'
        path += os.path.abspath(os.path.join(self.tool_dir, 'bin'))
        os.environ['PATH'] = path

        return True

    def default_x64_tools(self):
        host_proc = os.environ['PROCESSOR_ARCHITECTURE']
        if host_proc != 'AMD64' and host_proc != 'x86':
            self.print_both("error: Only x86 and x64 host processor architectures are supported for Visual C++.")
            return False

        if host_proc == 'AMD64':
            self.cl   = os.path.join(self.tool_dir, 'bin', 'amd64', 'cl.exe')
            self.link = os.path.join(self.tool_dir, 'bin', 'amd64', 'link.exe')
            self.lib  = os.path.join(self.tool_dir, 'bin', 'amd64', 'lib.exe')
        elif host_proc == 'x86':
            self.cl   = os.path.join(self.tool_dir, 'bin', 'x86_amd64', 'cl.exe')
            self.link = os.path.join(self.tool_dir, 'bin', 'x86_amd64', 'link.exe')
            self.lib  = os.path.join(self.tool_dir, 'bin', 'x86_amd64', 'lib.exe')

        if self.mfcatl_dir:
            self.builtin_include_list.append(os.path.join(self.mfcatl_dir, 'include'))
            self.builtin_libpath_list.append(os.path.join(self.mfcatl_dir, 'lib', 'amd64'))

        if self.winsdk_new_layout:
            # Windows 8 and newer SDKs
            self.rc = os.path.join(self.winsdk_dir, 'bin', 'x86', 'rc.exe')
            self.builtin_include_list.append(os.path.join(self.winsdk_dir, 'Include', 'shared'))
            self.builtin_include_list.append(os.path.join(self.winsdk_dir, 'Include', 'um'))
            self.builtin_libpath_list.append(os.path.join(self.winsdk_dir, 'Lib', 'winv6.3', 'um', 'x64'))
        else:
            # Windows 7 and older SDKs
            self.rc = os.path.join(self.winsdk_dir, 'bin', 'rc.exe')
            self.builtin_include_list.append(os.path.join(self.winsdk_dir, 'include'))
            self.builtin_libpath_list.append(os.path.join(self.winsdk_dir, 'lib', 'x64'))

        # Add the C standard library
        self.builtin_include_list.append(os.path.join(self.tool_dir, 'include'))
        self.builtin_libpath_list.append(os.path.join(self.tool_dir, 'lib', 'amd64'))

        # Visual C++ needs to access dlls scattered through the installation, so add to the PATH.
        path = os.environ['PATH']
        if path[-1] != ';':
            path += ';'
        path += os.path.abspath(os.path.join(self.tool_dir, os.pardir, 'Common7', 'IDE'))
        path += ';'
        if host_proc == 'AMD64':
            path += os.path.abspath(os.path.join(self.tool_dir, 'bin', 'amd64'))
        elif host_proc == 'x86':
            path += os.path.abspath(os.path.join(self.tool_dir, 'bin'))
        os.environ['PATH'] = path

        return True

    def compile(self, name, config, output_dir, rebuild_list, include_list, define_list):
        # Build the basic compiler invocation command line arguments
        compile_flags = ['"' + self.cl + '"',
                         '/nologo',            # do not output complier version string
                         '/c',                 # compile only. No link on cl.exe invoke
                         '/W4',                # set the warning level to the maximum
                         '/WX',                # treat warnings as errors
                         '/Zi',                # generate full symbol information (pdb)
                         '/EHsc',              # enable C++ exception handling (and assume extern "C" is nothrow)
                         '/fp:fast',           # sacrifice 100% float compliance for speed
                         '/showIncludes',      # print include files to stderr
                         '/TP',                # compile everything as C++
                         '/X']                 # ignore standard include paths
        compile_flags.extend(self.target_compile_flags())
        if config == 'debug':
            compile_flags.extend(['/Od',       # disable optimizations
                                  '/MTd',      # multithreaded c++ debug library
                                  '/RTCscu'])  # enable all runtime checking
        else:
            compile_flags.extend(['/MT',       # multithreaded c++ library
                                  '/GL',       # whole program optimizations
                                  '/O1',       # maximum speed optimization
                                  '/GS-'])     # disable stack overflow checking

        rc_flags = ['"' + self.rc + '"',
                    '/nologo',                 # do not output rc version string
                    '/X']                      # Ignore standard include poaths

        for define in define_list:
            compile_flags.append('/D' + define)
            rc_flags.append('/D' + define)

        for include_dir in include_list:
            compile_flags.append('/I"' + include_dir + '"')
            rc_flags.append('/I"' + include_dir + '"')

        for include_dir in self.builtin_include_list:
            compile_flags.append('/I"' + include_dir + '"')
            rc_flags.append('/I"' + include_dir + '"')

        compile_flags.append('/Fd"' + os.path.join(output_dir, name + '.pdb"'))

        did_pch = False
        did_rc = False
        for r in rebuild_list:
            source_split = os.path.split(r.source)
            source_name_split = os.path.splitext(source_split[1])
            source_base_name = source_name_split[0]
            source_extension = source_name_split[1]

            if source_base_name.lower() == 'precomp':
                if did_pch:
                    self.handle_error("error: found multiple precompiled header source files")

                # Super-naive C++ parsing; assume the precompiled header source file includes
                # ONE file only.
                precomp_match = None
                with open(r.source, 'r') as precomp_file:
                    precomp_text = precomp_file.read()
                    precomp_match = re.search(r'#include\s*[<"](.*)[>"]', precomp_text)

                if not precomp_match:
                    self.handle_error("error: Can not parse precompiled header source file")

                precompiled_header = precomp_match.group(1)
                precompiled_binary = os.path.join(output_dir, name + '.intermediates', source_base_name + '.pch')

                invocation_flags = copy.copy(compile_flags)
                invocation_flags.extend(['/Yc"' + precompiled_header + '"',
                                         '/Fp"' + precompiled_binary + '"',
                                         '/Fo"' + r.obj + '"',
                                         '"' + r.source + '"'])

                compile_flags.extend(['/Yu"' + precompiled_header + '"',
                                      '/Fp"' + precompiled_binary + '"'])

                # Run it
                self.print_both("building precompiled header")
                i = self.invoke(invocation_flags)
                self.handle_compiler_invoke_result(i, r.dep)

                # Do not compile the precompiled header source file again
                rebuild_list.remove(r)
                did_pch = True
            elif source_extension.lower() == '.rc':
                if did_rc:
                    # This is a Microsoft linker limitation
                    self.handle_error("error: found multiple resource source files")

                invocation_flags = copy.copy(rc_flags)
                invocation_flags.extend(['/Fo"' + r.obj + '"',
                                         '"' + r.source + '"'])

                # Run it
                self.print_both("resource compile %s" % source_split[1])
                i = self.invoke(invocation_flags)
                if i.return_val != 0:
                    self.handle_error(i.stdout)

                rebuild_list.remove(r)
                did_rc = True

        for r in rebuild_list:
            # Finish the flags for this particular compiler invocation
            invocation_flags = copy.copy(compile_flags)
            invocation_flags.extend(['/Fo"' + r.obj + '"',
                                     '"' + r.source + '"'])

            # Run it
            self.print_both("compiling %s" % os.path.basename(r.source))
            i = self.invoke(invocation_flags)
            self.handle_compiler_invoke_result(i, r.dep)

    def handle_compiler_invoke_result(self, i, deps_file_name):
        # Visual C++ interleaves the header list we use for deps files into the normal output
        stdout_split = self.split_cl_output(i.stdout)

        if i.return_val != 0:
            self.handle_error(stdout_split[visual_cpp.split_includes_text_index])

        # Write the dependent information into the .dep file
        with open(deps_file_name, 'w') as deps_file:
            deps_file.write(stdout_split[visual_cpp.split_includes_deps_index])

    def split_cl_output(self, compiler_output):
        # Parse out the dependent header file information. Remmove duplicates.
        headers = []
        text = []
        unique_headers = set()
        compiler_output_lines = compiler_output.splitlines()
        for line in compiler_output_lines:
            partiton = line.partition('Note: including file:')
            if partiton[1]:
                header = partiton[2].strip().lower()
                if not header in unique_headers:
                    unique_headers.add(header)
                    headers.append(header)
            else:
                text.append(partiton[0])

        return ('\n'.join(text), '\n'.join(headers))

    def link_static_lib(self, name, output_dir, config, built_code):
        lib_name = self.get_lib_name(name)
        lib_path = os.path.join(output_dir, lib_name)

        if not built_code and os.path.isfile(lib_path):
            self.print_both("%s is up to date" % lib_name)
            return

        lib_flags = ['"' + self.lib + '"']

        object_code_dir = os.path.join(output_dir, name + '.intermediates', "obj")
        for root, dirs, files in os.walk(object_code_dir, topdown=True):
            for filename in files:
                lib_flags.append('"' + os.path.join(root, filename) + '"')

        lib_flags.append('/OUT:"' + lib_path + '"')

        self.print_both("linking %s" % lib_name)
        i = self.invoke(lib_flags)
        if i.return_val != 0:
            self.handle_error(i.stdout)

    def link_module(self, name, output_dir, config, built_code, link_module_type, libpath_list, lib_list):
        link_name = self.get_link_name(name, link_module_type)
        link_path = os.path.join(output_dir, link_name)
        link_libpath_list = copy.copy(libpath_list)
        link_libpath_list.extend(self.builtin_libpath_list)

        if not built_code and not self.check_for_link_update(link_path, link_libpath_list, lib_list):
            self.print_both("%s is up to date" % link_name)
            return

        link_flags = ['"' + self.link + '"',
                      '/NOLOGO',         # do not output linker version string
                      '/WX',             # treat link warnings as errors
                      '/INCREMENTAL:NO', # control incremental linking
                      '/MAP',            # generate a .map output file
                      '/DEBUG',          # generate debug information
                      '/NODEFAULTLIB',   # ignore default libs
                      '/SWAPRUN:NET',    # ensure the image is copied to memory when loaded over CD or net
                      '/SWAPRUN:CD',
                      '/DYNAMICBASE',    # use address space layout randomization
                      '/NXCOMPAT',       # compatible with Data Execution Prevention
                      '/MANIFEST']       # generate manifest with default UAC and SxS settings
        link_flags.extend(self.target_link_flags(link_module_type))
        if config != 'debug':
            link_flags.extend(['/OPT:REF',  # remove unreferenced comdats
                               '/OPT:ICF',  # identical comdat folding
                               '/LTCG'])    # link-time code generation
        if config == 'ship':
            link_flags.append('/RELEASE')   # set the checksum in the image header

        for libpath_dir in link_libpath_list:
            link_flags.append('/LIBPATH:"' + libpath_dir + '"')

        link_flags.append('/OUT:"' + link_path + '"')

        object_code_dir = os.path.join(output_dir, name + '.intermediates', "obj")
        for root, dirs, files in os.walk(object_code_dir, topdown=True):
            for filename in files:
                link_flags.append('"' + os.path.join(root, filename) + '"')

        for lib in lib_list:
            link_flags.append(self.get_lib_name(lib))

        if config == 'debug':
            link_flags.extend(['libcpmtd.lib', 'libcmtd.lib'])
        else:
            link_flags.extend(['libcpmt.lib', 'libcmt.lib'])

        self.print_both("linking %s" % link_name)
        i = self.invoke(link_flags)
        if i.return_val != 0:
            self.handle_error(i.stdout)

    def get_lib_name(self, name):
        return name + '.lib'

    def get_link_name(self, name, link_module_type):
        if link_module_type == compiler.link_module_type_shared:
            return name + '.dll'
        elif link_module_type == compiler.link_module_type_application:
            return name + '.exe'
        else:
            self.handle_error("error: invalid module link type")

    def target_link_flags(self, link_module_type):
        link_flags = self.machine_link_flags()
        if link_module_type == compiler.link_module_type_shared:
            link_flags.append('/DLL')
        elif link_module_type == compiler.link_module_type_application:
            link_flags.append('/SUBSYSTEM:CONSOLE')
        else:
            self.handle_error("error: invalid module link type")
        return link_flags

class visual_cpp_2008(visual_cpp):
    def get_vs_common_tools_var(self):
        return 'VS90COMNTOOLS'

class visual_cpp_2008_x86(visual_cpp_2008):
    def target_proc(self):
        return 'x86'

    def detect(self):
        if not visual_cpp_2008.detect(self):
            return False

        return self.default_x86_tools()

    def target_compile_flags(self):
        return ['/arch:SSE2']

    def machine_link_flags(self):
        return ['/MACHINE:X86']

class visual_cpp_2008_x64(visual_cpp_2008):
    def target_proc(self):
        return 'x64'

    def detect(self):
        if not visual_cpp_2008.detect(self):
            return False

        return self.default_x64_tools()

    def target_compile_flags(self):
        return []

    def machine_link_flags(self):
        return ['/MACHINE:X64']

class visual_cpp_2010(visual_cpp):
    def get_vs_common_tools_var(self):
        return 'VS100COMNTOOLS'

class visual_cpp_2010_x86(visual_cpp_2010):
    def target_proc(self):
        return 'x86'

    def detect(self):
        if not visual_cpp_2010.detect(self):
            return False

        return self.default_x86_tools()

    def target_compile_flags(self):
        return ['/arch:SSE2']

    def machine_link_flags(self):
        return ['/MACHINE:X86']

class visual_cpp_2010_x64(visual_cpp_2010):
    def target_proc(self):
        return 'x64'

    def detect(self):
        if not visual_cpp_2010.detect(self):
            return False

        return self.default_x64_tools()

    def target_compile_flags(self):
        return []

    def machine_link_flags(self):
        return ['/MACHINE:X64']

class visual_cpp_2013(visual_cpp):
    def get_vs_common_tools_var(self):
        return 'VS120COMNTOOLS'

class visual_cpp_2013_x86(visual_cpp_2013):
    def target_proc(self):
        return 'x86'

    def detect(self):
        if not visual_cpp_2013.detect(self):
            return False

        return self.default_x86_tools()

    def target_compile_flags(self):
        return ['/arch:SSE2']

    def machine_link_flags(self):
        return ['/MACHINE:X86']

class visual_cpp_2013_x64(visual_cpp_2013):
    def target_proc(self):
        return 'x64'

    def detect(self):
        if not visual_cpp_2013.detect(self):
            return False

        return self.default_x64_tools()

    def target_compile_flags(self):
        return []

    def machine_link_flags(self):
        return ['/MACHINE:X64']
