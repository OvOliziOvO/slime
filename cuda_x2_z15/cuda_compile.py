"""Compile standalone CUDA PTX with the driver toolchain."""
import ctypes as c
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from .scalar_mma import lower_binary_mma

RELEASE_ARCHS = (61, 75, 86, 89, 120)


def target_program(program, arch):
    if isinstance(program, bytes):
        program = program.decode()
    if arch < 80:
        program = lower_binary_mma(program)
    version = "8.7" if arch >= 100 else "8.0"
    return program.replace(".version 8.0", f".version {version}", 1).replace(
        ".target sm_86", f".target sm_{arch}", 1
    ).encode()


def compile_cubin(ptx, arch, ptxas=None):
    if ptxas is not None or sys.platform == "win32":
        assembler = ptxas or shutil.which("ptxas")
        if assembler is None:
            raise RuntimeError("Install CUDA Toolkit or pass the path to ptxas.")
        with TemporaryDirectory(prefix="slime-ptx-") as directory:
            source = Path(directory) / "kernel.ptx"
            target = source.with_suffix(".cubin")
            source.write_bytes(ptx)
            subprocess.run(
                [str(assembler), f"-arch=sm_{arch}", "-O3", "-o", str(target), str(source)],
                check=True,
            )
            return target.read_bytes()
    compiler = c.CDLL("libnvidia-ptxjitcompiler.so.1")
    handle = c.c_void_p()
    compiler.nvPTXCompilerCreate.argtypes = [c.POINTER(c.c_void_p), c.c_size_t, c.c_char_p]
    compiler.nvPTXCompilerCompile.argtypes = [c.c_void_p, c.c_int, c.POINTER(c.c_char_p)]
    if compiler.nvPTXCompilerCreate(c.byref(handle), len(ptx), ptx):
        raise RuntimeError("Could not create the NVIDIA PTX compiler")
    try:
        flags = (c.c_char_p * 3)(f"--gpu-name=sm_{arch}".encode(), b"--opt-level=3", b"--verbose")
        if compiler.nvPTXCompilerCompile(handle, len(flags), flags):
            log_size = c.c_size_t()
            compiler.nvPTXCompilerGetErrorLogSize(handle, c.byref(log_size))
            log = c.create_string_buffer(log_size.value)
            compiler.nvPTXCompilerGetErrorLog(handle, log)
            raise RuntimeError(log.value.decode(errors="replace"))
        size = c.c_size_t()
        if compiler.nvPTXCompilerGetCompiledProgramSize(handle, c.byref(size)):
            raise RuntimeError("Could not get cubin size")
        data = c.create_string_buffer(size.value)
        if compiler.nvPTXCompilerGetCompiledProgram(handle, data):
            raise RuntimeError("Could not read cubin")
        return data.raw
    finally:
        compiler.nvPTXCompilerDestroy(c.byref(handle))


def cubin_path(program, arch):
    name = sha256(program).hexdigest() + ".cubin"
    return Path(__file__).resolve().with_name("cubin") / f"sm_{arch}" / name


def module_image(program, arch):
    if arch in RELEASE_ARCHS:
        image = target_program(program, arch)
        path = cubin_path(image, arch)
        if path.is_file():
            return path.read_bytes()
    # Load virtual PTX for source checkouts and compatible unlisted devices.
    return target_program(program, 61 if arch < 80 else 80) + b"\0"
