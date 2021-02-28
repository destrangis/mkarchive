"""Create a self extracting executable
"""
import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

try:
    from importlib.resources import read_text, files
except ImportError:
    from importlib_resources import read_text, files

from . import VERSION
import installer

# we need the module name to locate its resources
MODULE = __name__.split(".")[0]

DEFAULT_LIBTAR_A = "/usr/lib/x86_64-linux-gnu/libtar.a"
DEFAULT_LIBZ_A = "/usr/lib/x86_64-linux-gnu/libz.a"
DEFAULT_TAR_NAME = "_tmp.tar.gz"
DEFAULT_SELF_EXTRACTOR_NAME = "selfextract"
DEFAULT_SETUP_NAME = "setup.sh"
SELF_EXTRACTOR_SRC = "selfextract0.c"
SELF_EXTRACTOR = "selfextract1"
CHUNKSIZE = 1024 * 1024


def create_tar(filelst, tarname=DEFAULT_TAR_NAME, workdir="."):
    print(f"Creating tar '{tarname}'")
    with tarfile.open(tarname, "w:gz", format=tarfile.GNU_FORMAT) as tar:
        for f in filelst:
            tar.add(f)

        if "setup" not in filelst:
            print("Adding default 'setup' program")
            setup = files(MODULE) / DEFAULT_SETUP_NAME
            tar.add(str(setup), "setup")


def make_executable(src, exename, libtar=None, zlib=None, cppdefs=None, debug=False):
    if debug:
        opt = "-g"
    else:
        opt = "-O3"

    # We prefer static linking using the .a version of libtar & libz, as
    # they may not be installed on the target system
    if libtar is None:
        libtar = DEFAULT_LIBTAR_A
        # libtar = "-ltar"  # this would create a dynamic link
    if zlib is None:
        zlib = DEFAULT_LIBZ_A
        # zlib = "-lz"  # this would create a dynamic link

    cpplst = []
    if cppdefs is not None:
        for k, v in cppdefs.items():
            if v is None:
                cpplst.append(f"-D{k}")
            else:
                cpplst.append(f"-D{k}={v}")

    if sys.platform.lower().startswith("linux"):
        p = subprocess.run(
            [
                "gcc",
                opt,
                "-o",
                str(exename),
            ]
            + cpplst
            + [str(src), libtar, zlib]
        )
        if p.returncode:
            raise RuntimeError(
                f"Couldn't build self extractor '{exename}' from '{src}'"
            )
    else:
        raise NotImplementedError(f"Platform '{sys.platform}' not (yet) supported.")


def create_self_extractor(libtar, libz, workdir):
    print(f"Creating {SELF_EXTRACTOR}")
    selfext = workdir / SELF_EXTRACTOR
    src = workdir / SELF_EXTRACTOR_SRC

    with src.open("w") as sd:
        sd.write(read_text(MODULE, SELF_EXTRACTOR_SRC))

    # shutil.copy(SELF_EXTRACTOR_PATTERN, src)

    make_executable(src, selfext, libtar, libz)

    size = selfext.stat().st_size
    print(f"{selfext} created with size {size}")

    # edit_file_size(src, size)

    print(f"Recompiling {src}")
    make_executable(src, selfext, libtar, libz,
                    cppdefs={"THIS_FILE_SIZE": str(size)})

    if size != selfext.stat().st_size:  # sanity check
        raise RuntimeError("Size mismatch on output executable!")

    src.unlink()  # not needed any more
    print(f"Size of {selfext} matches {size}")
    return selfext


def writefile(outfd, path):
    print(f"Adding {path}")
    with path.open("rb") as fd:
        chunk = fd.read(CHUNKSIZE)
        while chunk:
            outfd.write(chunk)
            chunk = fd.read(CHUNKSIZE)


def cat_exe_archive(name, archive, output):
    print(f"Concatenating {name} and {archive} into {output}")
    with output.open("wb") as out:
        writefile(out, name)
        writefile(out, archive)
    output.chmod(0o755)


def cleanup(*files):
    print("Cleaning up...")
    for f in files:
        print(f"  removing '{f}'")
        os.remove(f)


def create_installer(options):
    varlst = options.var or []
    varmap = {}
    for v in varlst:
        kv = v.split("=", 1)
        key = kv[0]
        val = kv[1] if len(kv) > 1 else None
        varmap[key] = val

    installer.create_installer(
        options.install_spec,
        "setup",
        options.uname,
        dialog=options.dialog_tool,
        vars=varmap,
    )

    if "setup" not in options.file:
        options.file.append("setup")


def parse_cmdline(argv):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--version",
        action="store_true",
        default=False,
        help="Print version and exit"
    )
    p.add_argument(
        "--output",
        "-o",
        metavar="name",
        default=DEFAULT_SELF_EXTRACTOR_NAME,
        help="Name of the output self-extractor. Default "
        f"'{DEFAULT_SELF_EXTRACTOR_NAME}'",
    )
    p.add_argument(
        "--libtar",
        "-l",
        metavar="libtar-location",
        default=DEFAULT_LIBTAR_A,
        help=f"Location of libtar.a for linking. Default '{DEFAULT_LIBTAR_A}'",
    )
    p.add_argument(
        "--zlib",
        "-z",
        metavar="zlib-location",
        default=DEFAULT_LIBZ_A,
        help=f"Location of zlib.a for linking. Default '{DEFAULT_LIBZ_A}'",
    )
    p.add_argument(
        "--install-spec",
        "-i",
        metavar="install-spec",
        help="Installer specification in YAML",
    )
    p.add_argument(
        "--tmpdir",
        "-t",
        metavar="tmpdir",
        default=os.getenv("TMP", "/tmp"),
        help="Work directory. Default $TMP or /tmp",
    )
    p.add_argument(
        "--uname",
        "-u",
        metavar="uninstaller-name",
        default="uninstall",
        help="Name of the uninstaller script. Default 'uninstall'",
    )
    p.add_argument(
        "--dialog-tool",
        "-d",
        metavar="dialog-tool",
        default="dialog",
        help="Name of the dialog tool. Default 'dialog'",
    )
    p.add_argument(
        "--var",
        "-v",
        metavar="varname[=value]",
        action="append",
        help="Define variable and its value for use in the installer script",
    )
    p.add_argument("file", nargs="*", help="Files and directories to archive")
    return p.parse_args(argv)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    options = parse_cmdline(argv)

    if options.version:
        print(VERSION)
        return 0

    if not options.file:
        print("No files specified for the archive.")
        return 1

    if options.install_spec:
        create_installer(options)

    with tempfile.TemporaryDirectory(dir=options.tmpdir) as tmpdir:
        workdir = pathlib.Path(tmpdir)

        tarname = workdir / DEFAULT_TAR_NAME
        create_tar(options.file, tarname)
        tempextractor = create_self_extractor(options.libtar, options.zlib, workdir)
        cat_exe_archive(tempextractor, tarname, pathlib.Path(options.output))

    return 0

if __name__ == "__main__":
    sys.exit(main())
