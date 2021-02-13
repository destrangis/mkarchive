from io import StringIO

import yaml

DIALOG="dialog"

CHECK_CANCEL = """
function check_cancel {{
        if [ $1 -eq 255 -o $1 -eq 1 ]; then
            {} --title "Confirm" --yesno "Are you sure you want to quit?" 0 0
            if [ $? -eq 0 ]; then
                rm $tmpfile
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
        raise RuntimeError(f"{config_file} must must be a mapping "
                            "containing at least an 'install' key")

    return cfgcontent

def write_screen(fd, scr):
    scr_type = scr.get("type")
    if not scr_type:
        RuntimeError(f"{pformat(scr)}\nMust have a 'type' field")
    title = scr.get("title")
    title = f'"{title}"' if title else None
    condition = scr.get("condition")
    text = scr.get("text", "Screen Intentionally Blank")
    options = scr.get("options", [])
    store_var = scr.get("store")
    store_val = "$"+store_var if store_var else None
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
          + f"{DIALOG} {' '.join('--' + opt for opt in options)} \\\n"
          + ("" if not title else f"  --title {title} \\\n")
          + f"  --{scr_type} \"{text}\" \\\n"
          + f"  0 0 { store_val or '' } 2> $tmpfile\n"
          + "exitval=$?\n"
          + "check_cancel $exitval\n"
          + (f"{store_var}=$(cat $tmpfile)\n" if store_var else "")
          + (f"{after}\n" if after else "")
          + ("fi\n" if condition else "")
          + "\n")


def start_script(fd):
    fd.write("#!/bin/bash\n")
    fd.write("set -euo pipefail\n")
    fd.write(CHECK_CANCEL.format(DIALOG))
    fd.write("pid=$BASHPID\n")
    fd.write("tmpfile=/tmp/response_$pid\n")


def create_uninstaller(scrlst):
    with StringIO() as outfd:
        start_script(outfd)
        outfd.write("rootdir=$(dirname $0)\n")
        for scr in scrlst:
            write_screen(outfd, scr)
        outfd.write("rm $tmpfile\n")
        outfd.write("rm $0\n\n")
        return outfd.getvalue()


def create_installer(config_file, name):
    config = loaddef(config_file)

    uninstalling = "uninstall" in config
    if uninstalling:
        uninst_code = create_uninstaller(config["uninstall"])

    scrlst = config["install"]
    with open(name, "w") as fd:
        start_script(fd)
        fd.write("rootdir=$1\n")
        if uninstalling:
            fd.write(f"uninstaller_name=uninstall_$(basename {name})\n")
        for scr in scrlst:
            write_screen(fd, scr)
        fd.write("rm $tmpfile\n")
        if uninstalling:
            fd.write("cat <<EOF >$destdir/$uninstaller_name\n")
            fd.write(escape_text(uninst_code))
            fd.write("EOF\n\n")
