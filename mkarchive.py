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


HERE = pathlib.Path(__file__).parent

DEFAULT_LIBTAR_A            = "/usr/lib/x86_64-linux-gnu/libtar.a"
DEFAULT_LIBZ_A              = "/usr/lib/x86_64-linux-gnu/libz.a"
DEFAULT_TAR_NAME            = "_tmp.tar.gz"
DEFAULT_SELF_EXTRACTOR_NAME = "selfextract"
SELF_EXTRACTOR_SRC          = HERE / "selfextract0.c"
SELF_EXTRACTOR              = HERE / "selfextract1"
CHUNKSIZE                   = 1024 * 1024


def create_tar(filelst, tarname=DEFAULT_TAR_NAME):
    print(f"Creating tar '{tarname}'")
    with tarfile.open(tarname, "w:gz", format=tarfile.GNU_FORMAT) as tar:
        for f in filelst:
            tar.add(f)


def make_executable(src, exename,
                    libtar=None,
                    zlib=None,
                    cppdefs=None,
                    debug=False):
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
        p = subprocess.run(["gcc", opt, "-o", str(exename),]
                            + cpplst + [str(src), libtar, zlib])
        if p.returncode:
            raise RuntimeError(
                f"Couldn't build self extractor '{exename}' from '{src}'"
            )
    else:
        raise NotImplementedError(f"Platform '{sys.platform}' not (yet) supported.")


def create_self_extractor(libtar, libz):
    print(f"Creating {SELF_EXTRACTOR}")
    selfext = SELF_EXTRACTOR
    src = SELF_EXTRACTOR_SRC

    #shutil.copy(SELF_EXTRACTOR_PATTERN, src)

    make_executable(src, selfext, libtar, libz)

    size = selfext.stat().st_size
    print(f"{selfext} created with size {size}")

    #edit_file_size(src, size)

    print(f"Recompiling {src}")
    make_executable(src, selfext, libtar, cppdefs={"THIS_FILE_SIZE": str(size)})

    if size != selfext.stat().st_size:  # sanity check
        raise RuntimeError("Size mismatch on output executable!")

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


def parse_cmdline(argv):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--output",
        "-o",
        metavar="name",
        default="selfextract",
        help="Name of the output self-extractor. Default "
        f"'{DEFAULT_SELF_EXTRACTOR_NAME}'",
    )
    # p.add_argument("--run", "-r", metavar="program",
    # help="Executable program or script to run after extraction")
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
    p.add_argument("file", nargs="+", help="Files and directories to archive")
    return p.parse_args(argv)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    options = parse_cmdline(argv)

    tarname = pathlib.Path(DEFAULT_TAR_NAME)
    create_tar(options.file, tarname)
    tempextractor = create_self_extractor(options.libtar, options.zlib)
    cat_exe_archive(tempextractor, tarname, pathlib.Path(options.output))
    cleanup(tempextractor, tarname)


if __name__ == "__main__":
    main()
