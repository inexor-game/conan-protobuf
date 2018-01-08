from conans import ConanFile, CMake, tools
from conans.util.files import load  #, save
import os
import sys
import re


class ProtobufConan(ConanFile):
    name = "Protobuf"
    version = "3.5.1"
    description = "Protocol Buffers - Google's data interchange format"
    url = "https://github.com/inexorgame/conan-protobuf.git"
    license = "https://github.com/google/protobuf/blob/v{}/LICENSE".format(version)
    requires = "zlib/1.2.11@conan/stable"
    settings = "os", "compiler", "build_type", "arch"
    # exports = "CMakeLists.txt", "lib*.cmake", "extract_includes.bat.in", "protoc.cmake", "tests.cmake", "change_dylib_names.sh"
    options = {"shared": [True, False]}
    default_options = "shared=False"
    generators = "cmake"
    folder = "protobuf-{}".format(version)

    def replace_in_file_regex(self, file_path, regex, replace):
        # TODO: FIXME: Dear Future-ourselves, forgive us. We had good intentions.
        if sys.version_info[0] > 2:
            # py3k
            with open(file_path, "r+t") as handle:
                content = handle.read()
                content = re.sub(regex, replace, content)
                handle.write(content)
                handle.close()
        else: # python 2.x
            content = load(file_path)
            content = content.encode("utf-8")
            content = re.sub(regex.encode("utf-8"), replace, content)
            with open(file_path, "wb") as handle:
                handle.write(content)
                handle.close()

    def config(self):
        self.options["zlib"].shared = self.options.shared

    def source(self):
        tools.download("https://github.com/google/protobuf/"
                       "releases/download/v{0}/protobuf-cpp-{0}.zip".format(self.version),
                       "protobuf.zip")
        tools.unzip("protobuf.zip")
        os.unlink("protobuf.zip")
        tools.replace_in_file("{}/cmake/CMakeLists.txt".format(self.folder), "project(protobuf C CXX)", '''project(protobuf C CXX)
include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()''')
        tools.replace_in_file("{}/cmake/install.cmake".format(self.folder),
                              'set(CMAKE_INSTALL_CMAKEDIR "${CMAKE_INSTALL_LIBDIR}/cmake/protobuf" CACHE STRING "${_cmakedir_desc}")',
                              'set(CMAKE_INSTALL_CMAKEDIR "cmake" CACHE STRING "${_cmakedir_desc}")') # Install to the same folder for all compilers.

    def build(self):
        args = ["-Dprotobuf_BUILD_TESTS=OFF", "-Dprotobuf_BUILD_EXAMPLES=OFF"]
        args += ["-DCMAKE_INSTALL_PREFIX={}/install".format(os.getcwd())] # We do install, since we need some cmake files
        args += ["-DBUILD_SHARED_LIBS={}".format('ON' if self.options.shared else 'OFF')]
        args += ["-Dprotobuf_WITH_ZLIB=ON"]
        if self.settings.compiler == "Visual Studio":
            if self.settings.compiler.runtime == "MT" or self.settings.compiler.runtime == "MTd":
                args += ["-Dprotobuf_MSVC_STATIC_RUNTIME=ON"]
            else:
                args += ["-Dprotobuf_MSVC_STATIC_RUNTIME=OFF"]
        cmake = CMake(self)
        self.run('cmake {}/cmake {} {}'.format(self.folder, cmake.command_line, ' '.join(args)))
        self.output.warn("CMAKE OUTPUT: {}".format(cmake.command_line))
        self.run("cmake --build . {} --target install".format(cmake.build_config))

    def package(self):
        # Install FindProtobuf files:
        # Fix some hard paths first:
        self.replace_in_file_regex("install/cmake/protobuf-targets.cmake", 'INTERFACE_LINK_LIBRARIES ".+zlib.+"', 'INTERFACE_LINK_LIBRARIES "${ZLIB_LIBRARY}"')
        tools.replace_in_file("install/cmake/protobuf-targets.cmake", '''set_target_properties(protobuf::libprotobuf PROPERTIES''', '''find_package(ZLIB)
set_target_properties(protobuf::libprotobuf PROPERTIES''') # hard path to zlib.

        tools.replace_in_file("install/cmake/protobuf-targets.cmake", 'get_filename_component(_IMPORT_PREFIX "${_IMPORT_PREFIX}" PATH)', '''get_filename_component(_IMPORT_PREFIX "${_IMPORT_PREFIX}" PATH)
  set(_IMPORT_PREFIX "${CONAN_PROTOBUF_ROOT}")''') # search everything in the conan folder, not the install folder.
        tools.replace_in_file("install/cmake/protobuf-options.cmake", 'option(protobuf_MODULE_COMPATIBLE "CMake build-in FindProtobuf.cmake module compatible" OFF)',
        'option(protobuf_MODULE_COMPATIBLE "CMake build-in FindProtobuf.cmake module compatible" ON)') # We want to override the FindProtobuf.cmake shipped within CMake

        # Copy FindProtobuf.cmakes to package
        cmake_files = ["protobuf-config.cmake", "protobuf-config-version.cmake", "protobuf-options.cmake", "protobuf-module.cmake", "protobuf-targets.cmake"]
        for file in cmake_files:
            self.copy(file, dst=".", src="install/cmake/")
          # Copy the build_type specific file only for the right one:
        self.copy("protobuf-targets-{}.cmake".format("debug" if self.settings.build_type == "Debug" else "release"), dst=".", src="install/cmake/")

        # with open("install/cmake/protobuf-config.cmake", "r+t") as handle:
            # self.output.warn( handle.read()  )
            # handle.close()

        # Copy Headers to package include folder
        self.copy("*.h", dst="include", src="install/include")

        # Copy all proto files:
        self.copy("*.proto", dst="bin", src="{}/src".format(self.folder))

        # TODO: we should just use the stuff from the install folder directly.
        if self.settings.os == "Windows":
            self.copy("*.lib", dst="lib", src="lib", keep_path=False)
            self.copy("*.pdb", dst="lib", src="lib", keep_path=False)
            self.copy("protoc.exe", dst="bin", src="bin", keep_path=False)

            if self.options.shared:
                self.copy("*.dll", dst="bin", src="", keep_path=False)
        else:
            # Copy the libs to lib
            if not self.options.shared:
                self.copy("*.a", "", "install", keep_path=True)
            else:
                self.copy("*.so*", "", "install", keep_path=True)
                self.copy("*.9.dylib", "", "install", keep_path=True)

            # Copy the exe to bin
            # we need some sort of dynlib converter for macosx here, see memshardeds protobuf
            self.copy("protoc", "bin", "bin", keep_path=False)

    def package_info(self):
        basename = "libprotobuf"
        self.cpp_info.libdirs = ["lib", "lib64"]

        if self.settings.build_type == "Debug":
            basename = "libprotobufd"

        if self.settings.os == "Windows":
            self.cpp_info.libs = [basename]
            if self.options.shared:
                self.cpp_info.defines = ["PROTOBUF_USE_DLLS"]
        elif self.settings.os == "Macos":
            self.cpp_info.libs = [basename + ".a"] if not self.options.shared else [basename + ".9.dylib"]
        else:
            self.cpp_info.libs = [basename + ".a"] if not self.options.shared else [basename + ".so.9"]
