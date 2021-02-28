mkarchive
=========

Mkarchive is a self-executable archive generator for Linux. It generates
an archive in the form of an ELF executable file that, when executed,
will extract its contents to a temporary directory, and then run a
program called ``setup``, which *must* have been included with the
archive files.

It comes with ``smartsetup``, a utility that will generate a ``setup``
program for you, based on the ``dialog`` utility.

You may want to consider makeself_ as an alternative to this software.

.. _makeself: https://makeself.io/

Installing
----------

Mkarchive can be installed straight from PYPI using ``pip``::

    python3 -m pip install mkarchive

Requirements
------------

On the development machine, ``mkarchive`` requires the ``gcc`` compiler
to be in the path, and also ``libtar`` and ``zlib``.

On the target machine, it requires ``bash`` and ``libc6`` must be the
same version as  in the development machine. Also, depending on how you
created the archive, it might need ``libtar`` and ``zlib`` to be installed.
``mkarchive`` will try to link both libraries statically to relieve the
target machine of this requirement but, obviously, the archive will be
a little heavier as a result.

If you are using ``dialog`` or ``whiptail`` then it needs to be
installed on the target machine, or you may need to include it inside
your archive and provide a ``setup`` program that can find them.

Usage
-----

To simply create a self-extracting archive just use::

    $ mkarchive *

This will archive all the files and directories on the current working
directory and create the self-executable archive called ``selfextract``
also on the working directory.

If you want the archive to have a different name or to be created
elsewhere, you can use the ``--output``, or ``-o`` option::

    $ mkarchive -o ~/extractor.bin *

Note that the archives, as mentioned above, after unarchiving, will run
a user-supplied program called ``setup`` that must have been included on
the top level directory.

A minimal ``setup`` program could be::

    #!/bin/bash
    echo "Hello, I'm $0 called with $1 and the working directory is $(pwd)"

We can then create a minimal self-executable with it::

    $ mkarchive setup
    Creating tar '/tmp/tmpsqwogss0/_tmp.tar.gz'
    Creating selfextract1
    /tmp/tmpsqwogss0/selfextract1 created with size 104560
    Recompiling /tmp/tmpsqwogss0/selfextract0.c
    Size of /tmp/tmpsqwogss0/selfextract1 matches 104560
    Concatenating /tmp/tmpsqwogss0/selfextract1 and /tmp/tmpsqwogss0/_tmp.tar.gz into selfextract
    Adding /tmp/tmpsqwogss0/selfextract1
    Adding /tmp/tmpsqwogss0/_tmp.tar.gz

And then we can run the resulting ``selfextract`` archive::

    $ ./selfextract
    Hello, I'm /tmp/selfex__AvVAsz/setup called with /tmp/selfex__AvVAsz and the working directory is /home/javier

Your program will probably need to be a tad more sophisticated than this
one and will use the directory supplied as its first argument to do its
job.

If a ``setup`` program is not provided, mkarchive will
supply one for you that just copies the unarchived files and directories
to the user's current working directory.

Also, in the examples above, ``mkarchive`` has found ``libtar.a`` and
``libz.a`` on their default locations. You may want to specify a path to
these libraries using the ``--libtar`` and ``--zlib`` command line
options if you have your own compiled versions of these libraries, or
your distribution installs them at a different location than Ubuntu,
e.g::

    $ mkarchive --libtar /path/to/libtar.a --zlib /path/to/libz.a -o ~/extractor.bin setup file1 file2

You may link them dynamically by specifying ``-ltar`` and ``-lz``
respectively::

   $ mkarchive --lbitar=-ltar --zlib=-lz setup file1 file2


Generating the ``setup`` program
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``mkarchive`` can generate the ``setup`` program for you using the
included ``smartsetup`` utility. In order to do that you need to create
a YAML file containing a specification of the installer program. All it
does is to make it a bit easier to write an installer program using
``dialog`` screens.

Basically, the installer specification has two sections: the ``install``
section that contains the screens of the installer, and an ``uninstall``
section. Each of these two sections contain a list of objects that
correspond to parameters of the ``dialog`` utility, or a bash code
snippet, e.g::

    install:
      - type: inputbox
        title: Enter input file
        text: What file do you want to copy?
        store: filetocopy
        default: file1

      - type: inputbox
        title: Destination directory
        text: Enter the destination directory
        store: destdir

      - type: code
        text: cp -v $filetocopy $destdir

All types in the ``type`` field, except ``code`` correspond to dialog
types of the ``dialog`` utility, e.g ``inputbox``, ``yesno``, ``checklist``
etc. ``title`` is the ``--title`` option and ``text`` is the text. Other
options can be specified as a list in the ``options`` field.

When ``dialog`` would write a value to the error stream ``stderr`` you
can specify in the ``store`` field the  name of a variable to store it.
When the result is the program return code, you can check it using
``$exitval``.

The installer *must always* define the variable ``$destdir``, as it is
where the uninstaller program (if there is an ``uninstall`` section)
will be created.

The dialogs may be shown conditionally by putting a condition in the
``condition`` file. This should be the arguments of the ``test`` shell
command e.g::

    - title: Installation Successful
      type: msgbox
      condition: $success -eq 1
      text: The installation of $program $version has been successful.

Having ``mkarchive`` create the setup program
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``mkarchive`` accepts the ``--install-spec`` command line option to
specify the YAML file specification.

You can also use one or more ``--var`` options to pre-define variables
available to the installer program.

You can use ``--dialog-tool`` to specify the path (on the destination
machine with an absolute path, or inside the archive with a relative
path) of the ``dialog`` or ``whiptail`` command.

Finally, you can specify a name for the uninstaller program using the
``--uninstaller-name`` option::

    $ mkarchive --output ~/mysoft_installer.bin      \
            --install-spec=setup.yml                 \
            --uninstaller-name=mysoft_uninstall.bin  \
            --var=program=mysoft                     \
            --var=version=1.2                        \
            file1 file2 dir1

The ``smartsetup`` utility
~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``setup`` program can be generated independently of the
self-extracting archive using the ``smartsetup`` command with options
similar to the ones mentioned above::

    $ smartsetup --help
    usage: smartsetup [-h] [--name script-name] [--uname script-name]
                      [--dialog-tool dialog-tool] [--var varname[=value]]
                      spec

    Generate installer/uninstaller scripts from a YAML specification

    positional arguments:
      spec                  Input specification in YAML

    optional arguments:
      -h, --help            show this help message and exit
      --name script-name, -n script-name
                            Generate script with this name. Default 'setup'
      --uname script-name, -u script-name
                            Name of the uninstaller script. Default 'uninstall'
      --dialog-tool dialog-tool, -d dialog-tool
                            Name of the dialog tool. Default 'dialog'
      --var varname[=value], -v varname[=value]
                            Define variable and its value for use in the script

License
-------
This software is released under the MIT License
