#!/bin/sh

# Default setup program.
# Simply copy the files that have just been extracted to a temporary
# directory (which we get in $1) to the current directory.

tmpdir=$1
if [ -z "$tmpdir" ]; then
    echo "Error: No tmpdir argument passed to setup"
    exit 1
fi

echo "Copying files to current directory"
for item in $1/*
do
    if [ "$item" != "$1/setup" ]; then
        cp -rv $item .
    fi
done
