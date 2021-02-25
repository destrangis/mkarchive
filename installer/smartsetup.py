"""Generate installer/uninstaller scripts from a YAML specification
"""
import argparse
import os
import sys
from io import StringIO

import yaml

DIALOG = "dialog"

CHECK_CANCEL = """
function check_cancel {{
        if [ $1 -eq 255 -o $1 -eq 1 ]; then
            {} --title "Confirm" --yesno "Are you sure you want to quit?" 0 0
            if [ $? -eq 0 ]; then
                exit 1
            fi
        fi
    }}

"""


def escape_text(txt):
    escape_set = "\\$"  # make sure the \ gets escaped first!
    for c in escape_set:
        txt = txt.replace(c, "\\" + c)
    return txt


def loaddef(config_file):

    with open(config_file) as cfg:
        cfgcontent = yaml.load(cfg, Loader=yaml.Loader)
    if not isinstance(cfgcontent, dict) or "install" not in cfgcontent:
        raise RuntimeError(
            f"{config_file} must must be a mapping "
            "containing at least an 'install' key"
        )

    return cfgcontent


def write_screen(fd, scr, dialog):
    scr_type = scr.get("type")
    if not scr_type:
        RuntimeError(f"{pformat(scr)}\nMust have a 'type' field")
    title = scr.get("title")
    title = f'"{title}"' if title else None
    condition = scr.get("condition")
    text = scr.get("text", "Screen Intentionally Blank")
    options = scr.get("options", [])
    store_var = scr.get("store")
    store_val = "$" + store_var if store_var else None
    default = scr.get("default")
    after = scr.get("after")

    if scr_type == "code":
        fd.write("\n# USER CODE -----\n")
        fd.write(text + "\n")
        fd.write("# END USER CODE -----\n\n")
    else:
        fd.write(
            (f"if [ {condition} ]\nthen\n" if condition else "")
            + (f"{store_var}={default or ''}\n" if store_var else "")
            + "tmpfile=$(mktemp -q) && {\n"
            + f"{dialog} {' '.join('--' + opt for opt in options)} \\\n"
            + ("" if not title else f"  --title {title} \\\n")
            + f'  --{scr_type} "{text}" \\\n'
            + f"  0 0 { store_val or '' } 2> $tmpfile\n"
            + "exitval=$?\n"
            + "check_cancel $exitval\n"
            + (f"{store_var}=$(cat $tmpfile)\n" if store_var else "")
            + "rm $tmpfile\n"
            + "}\n"
            + (f"{after}\n" if after else "")
            + ("fi\n" if condition else "")
            + "\n"
        )


def start_script(fd, dialog, vars):
    fd.write("#!/bin/bash\n")
    fd.write("set -euo pipefail\n")
    fd.write(CHECK_CANCEL.format(dialog))
    fd.write("pid=$BASHPID\n")
    for key, val in vars.items():
        fd.write(key + "=" + (val or "") + "\n")
    fd.write("\n")


def create_uninstaller(scrlst, dialog, vars):
    with StringIO() as outfd:
        start_script(outfd, dialog, vars)
        outfd.write("rootdir=$(dirname $0)\n")
        for scr in scrlst:
            write_screen(outfd, scr, dialog)
        outfd.write("rm $0\n\n")
        return outfd.getvalue()


def create_installer(
    config_file, name, uninstaller="uninstall", dialog=DIALOG, vars=None
):
    if vars is None:
        vars = {}

    config = loaddef(config_file)

    uninstalling = "uninstall" in config
    if uninstalling:
        uninst_code = create_uninstaller(config["uninstall"], dialog, vars)

    scrlst = config["install"]
    with open(name, "w") as fd:
        start_script(fd, dialog, vars)
        fd.write("if [ $# -gt 1 ]; then\n")
        fd.write("   rootdir=$1\n")
        fd.write("else\n")
        fd.write("   rootdir=$(dirname $0)\n")
        fd.write("fi\n")
        if uninstalling:
            fd.write(f"uninstaller_name={uninstaller}\n")
        for scr in scrlst:
            write_screen(fd, scr, dialog)
        if uninstalling:
            fd.write("cat <<EOF >$destdir/$uninstaller_name\n")
            fd.write(escape_text(uninst_code))
            fd.write("EOF\n\n")
            fd.write("chmod +x $destdir/$uninstaller_name\n")

        os.chmod(name, 0o755)


def parse_cmdline(argv):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--name",
        "-n",
        metavar="script-name",
        default="setup",
        help="Generate script with this name. Default 'setup'",
    )
    p.add_argument(
        "--uname",
        "-u",
        metavar="script-name",
        default="uninstall",
        help="Name of the uninstaller script. Default 'uninstall'",
    )
    p.add_argument(
        "--dialog-tool",
        "-d",
        metavar="dialog-tool",
        default=DIALOG,
        help="Name of the dialog tool. Default 'dialog'",
    )
    p.add_argument(
        "--var",
        "-v",
        metavar="varname[=value]",
        action="append",
        help="Define variable and its value for use in the script",
    )
    p.add_argument("spec", help="Input specification in YAML")

    return p.parse_args(argv)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    options = parse_cmdline(argv)

    varlst = options.var or []
    varmap = {}
    for v in varlst:
        kv = v.split("=", 1)
        key = kv[0]
        val = kv[1] if len(kv) > 1 else None
        varmap[key] = val

    create_installer(
        options.spec,
        options.name,
        options.uname,
        dialog=options.dialog_tool,
        vars=varmap,
    )


if __name__ == "__main__":
    main()
