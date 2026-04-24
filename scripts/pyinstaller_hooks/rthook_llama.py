"""PyInstaller runtime hook — set library search path for llama_cpp native libs.

At freeze time, llama_cpp/lib/*.so files end up in _internal/llama_cpp/lib/.
The dynamic linker needs to find them there when libllama.so is loaded.
"""

import os
import sys

if getattr(sys, "frozen", False):
    base = sys._MEIPASS  # PyInstaller _internal directory
    llama_lib = os.path.join(base, "llama_cpp", "lib")
    if os.path.isdir(llama_lib):
        # Linux
        ld_path = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = llama_lib + (":" + ld_path if ld_path else "")
        # macOS
        dyld_path = os.environ.get("DYLD_LIBRARY_PATH", "")
        os.environ["DYLD_LIBRARY_PATH"] = llama_lib + (":" + dyld_path if dyld_path else "")
