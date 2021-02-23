#!/bin/sh

# Default setup program.
# Simply copy the files that have just been extracted to a temporary
# directory (which we get in $1) to the current directory.

echo "Copying files to current directory"
for item in $1/*
do
    if [ "$item" != "$1/setup" ]; then
        cp -rv $item .
    fi
done
