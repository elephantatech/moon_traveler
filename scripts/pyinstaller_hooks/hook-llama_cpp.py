"""PyInstaller hook for llama-cpp-python.

Ensures the native shared libraries in llama_cpp/lib/ are collected
and the runtime can find them via LD_LIBRARY_PATH / DYLD_LIBRARY_PATH.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# Collect all shared libraries from llama_cpp
datas = collect_data_files("llama_cpp")
binaries = collect_dynamic_libs("llama_cpp")
