
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <dirent.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <getopt.h>

#include "zlib.h"
#include "libtar.h"

#ifndef THIS_FILE_SIZE
#define THIS_FILE_SIZE   0
#endif

const char *prog_description = "Self executable archive and installer";

typedef struct st_optrec {
    char *longname;
    int has_arg;
    int shortopt;
    char *metavar;
    char *help;
} option_rec;

static option_rec option_descriptions[] = {
    {"help",    no_argument,       'h', NULL,"Print a help text and exit."},
    {"tmpdir",  required_argument, 't', "<dir>", "Use this temporary directory instead of /tmp or $TMP"},
    {"verbose", no_argument,       'v', NULL, "Print what's being done."},
    {"list",    no_argument,       'l', NULL, "Do not extract. Just show the list of files contained in archive."},
    {0, 0, 0, 0}
};

static struct {
    int help;
    char *tmpdir;
    int verbose;
    int list;
} options;

// return options as getopt_long() requires
static struct option *get_long_options()
{
    int i = 0;
    int count = 0;
    struct option *long_options;

    for (i = 0; option_descriptions[i].longname; i++) {
        count++;
    }

    long_options = (struct option *) malloc((count+1) * sizeof(struct option));
    for (i = 0; i < count; i++) {
        long_options[i].name = option_descriptions[i].longname;
        long_options[i].has_arg = option_descriptions[i].has_arg;
        long_options[i].flag = NULL;
        long_options[i].val = option_descriptions[i].shortopt;
    }
    long_options[count].name = NULL;
    long_options[count].has_arg = 0;
    long_options[count].flag = NULL;
    long_options[count].val = 0;

    return long_options;
}

static void help(char *progname)
{
    int i = 0;

    fprintf(stdout, "%s\n\n", prog_description);
    fprintf(stdout, "use: %s [options]\n\n", progname);
    fprintf(stdout, "options:\n");
    for (i = 0; option_descriptions[i].longname; i++) {
        if (option_descriptions[i].has_arg) {
            fprintf(stdout, "   --%s %s -%c %s\t%s",
                option_descriptions[i].longname,
                option_descriptions[i].metavar,
                option_descriptions[i].shortopt,
                option_descriptions[i].metavar,
                option_descriptions[i].help);
            }
        else {
            fprintf(stdout, "   --%s -%c\t%s",
                option_descriptions[i].longname,
                option_descriptions[i].shortopt,
                option_descriptions[i].help);
        }
        fprintf(stdout, "\n");
    }
    fprintf(stdout, "\n");
}


static int get_cmdline_args(int argc, char *argv[])
{
    char c;
    int option_index;
    int error = 0;
    struct option *long_options = get_long_options();

    options.help = 0;
    options.list = 0;
    options.tmpdir = NULL;
    options.verbose = 0;

    while (!error) {
        c = getopt_long(argc, argv, "vlt:h", long_options, &option_index);
        if (c == -1)
            break;

        switch (c) {
        case 'h':
            options.help = 1;
            break;
        case 'l':
            options.list = 1;
            break;
        case 'v':
            options.verbose = 1;
            break;
        case 't':
            options.tmpdir = optarg;
            break;
        case '?':
            error = 1;
        default:
            break;
        }
    }

    return error;
}

static char *fstring(const char *pattern, ...)
{
    char *newstring;
    size_t len;
    va_list arglst;

    va_start(arglst, pattern);
    len = vsnprintf(NULL, 0, pattern, arglst);
    va_end(arglst);

    newstring = malloc((len + 1) * sizeof(char));

    va_start(arglst, pattern);
    vsnprintf(newstring, len+1, pattern, arglst);
    va_end(arglst);

    return newstring;
}

static void say(const char *pattern, ...)
{
    va_list arglst;

    if (options.verbose) {
        va_start(arglst, pattern);
        vfprintf(stdout, pattern, arglst);
        va_end(arglst);
    }
}

static gzFile inputstream;
static const unsigned int GZIP_BUFFER_SIZE = (128*1024);
static int eof_found = 0;

int open_compressed(const char *filename, int mode, ...)
{
    int fd;

    say("Opening '%s'\n", filename);
    if (mode != O_RDONLY) {
        fprintf(stderr, "Error '%s' can only be opened in O_RDONLY(%d) "
                        "mode, not (%d)\n", filename, O_RDONLY, mode);
        return -1;
    }

    if ((fd = open(filename, O_RDONLY)) < 0) {
        fprintf(stderr, "Couldn't open '%s': [%d] %s\n", filename,
                                            errno, strerror(errno));
        return -1;
    }

    say("Setting position at %d\n", THIS_FILE_SIZE);
    if (lseek(fd, THIS_FILE_SIZE, SEEK_SET) < 0) {
        fprintf(stderr, "Error seeking [%d] %s\n", errno, strerror(errno));
        return -1;
    }

    inputstream = gzdopen(fd, "rb");
    if (NULL == inputstream) {
        fprintf(stderr, "Error setting up decompression\n");
        return -1;
    }

    if (gzbuffer(inputstream, GZIP_BUFFER_SIZE) < 0) {
        fprintf(stderr, "Couldn't allocate buffer size\n");
    }

    return fd;
}

ssize_t read_compressed(int fd, void *buffer, size_t len)
{
    int bytesread;
    int rc;

    if (eof_found)
        return 0;

    bytesread = gzread(inputstream, buffer, len);

    if (bytesread == -1) {
        gzerror(inputstream, &rc);
        fprintf(stderr, "Read error %d. ", rc);
        if (rc == Z_ERRNO) {
            // non-zlib error
            fprintf(stderr, "[%d] %s", errno, strerror(errno));
        }
        fprintf(stderr, "\n");
        return -1;
    }

    if (bytesread < len) {
        eof_found = 1;
    }

    return bytesread;
}

int close_compressed(int fd)
{
    int rc;

    rc = gzclose_r(inputstream);
    if (rc != Z_OK) {
        fprintf(stderr, "Error [%d] closing stream.", rc);
        if (rc == Z_ERRNO) {
            fprintf(stderr, " [%d] %s", errno, strerror(errno));
        }
        fprintf(stderr, "\n");
    }
    return rc == Z_OK? 0: -1;
}


static tartype_t gzfunpack = {
    open_compressed,
    close_compressed,
    read_compressed,
    NULL
};

static char * make_temp_dir()
{
    char *tmpdir = getenv("TMP");
    char *td;
    char *tdirname;
    int err;

    if (options.tmpdir) {
        tmpdir = options.tmpdir;
    } else if (NULL == tmpdir) {
        tmpdir = "/tmp";
    }

    td = fstring("%s/selfex__XXXXXX", tmpdir);
    tdirname = mkdtemp(td);
    if (tdirname == NULL) {
        fprintf(stderr, "Couldn't create temporary directory.\n");
        fprintf(stderr, "\t[%d] %s\n", errno, strerror(errno));
        free(td);
        return NULL;
    }

    return tdirname;
}


static int untar(char *filename, char *tmpdir)
{
    TAR *t;
    int rc;
    unsigned int verbose = options.verbose? TAR_VERBOSE: 0;

    say("Opening archive '%s'\n", filename);

    rc = tar_open(&t, filename, &gzfunpack, O_RDONLY, 0, verbose | TAR_GNU);
    if (rc < 0) {
        fprintf(stderr, "Cannot read tar file [%d] %s\n", errno, strerror(errno));
        return rc;
    }

    say("Extracting from tar into '%s'\n", tmpdir);
    rc = tar_extract_all(t, tmpdir);
    if (rc < 0) {
        fprintf(stderr, "Error extracting tar file [%d] %s\n", errno, strerror(errno));
        return rc;
    }

    tar_close(t);

    return 0;
}

static int list(char *filename)
{
    TAR *t;
    int rc;

    rc = tar_open(&t, filename, &gzfunpack, O_RDONLY, 0, TAR_GNU);
    if (rc < 0) {
        fprintf(stderr, "Cannot read tar file [%d] %s\n", errno, strerror(errno));
        return rc;
    }

    while (0 == (rc = th_read(t))) {
        th_print_long_ls(t);
        if (TH_ISREG(t))
            tar_skip_regfile(t);
    }

    tar_close(t);
    return 0;
}


static int run_setup(char *tmpdir)
{
    int rc;
    char *cmd = fstring("%s/setup %s", tmpdir, tmpdir);

    say("Running '%s'\n", cmd);
    rc = system(cmd);
    if (rc == -1) {
        fprintf(stderr, "Couldn't run setup [%d] %s\n", errno, strerror(errno));
    } else if (rc > 0) {
        fprintf(stderr, "Command setup failed rc = %d\n", rc);
    }
    return rc;
}


static int remove_tree(char *path)
{
    DIR *dir;
    struct dirent *entry;
    char *entryname;
    int rc;

    say("removing DIR '%s'\n", path);
    if (NULL == (dir = opendir(path))) {
        fprintf(stderr, "Cannot open '%s' [%d] %s\n",
                            path, errno, strerror(errno));
        return -1;
    }

    for (entry = readdir(dir);
            entry;
            entry = readdir(dir)) {
        entryname = fstring("%s/%s", path, entry->d_name);
        if (entry->d_type == DT_DIR) {
            if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) {
                continue;
            }
            rc = remove_tree(entryname);
            if (rc != 0)
                return rc;
        } else {
            say("removing FILE '%s'\n", entryname);
            rc = unlink(entryname);
            if (rc != 0) {
                fprintf(stderr, "Cannot remove '%s' [%d] %s\n",
                            entryname, errno, strerror(errno));
                return rc;
            }
        }
        free(entryname);
    }
    if (-1 == (rc = rmdir(path))) {
        fprintf(stderr, "Cannot remove directory '%s' [%d] %s\n",
                            path, errno, strerror(errno));
        return -1;
    }
    return 0;
}

static void cleanup(char *tmpdir)
{
    say("Cleaning up %s\n", tmpdir);
    remove_tree(tmpdir);
}

int main(int argc, char *argv[])
{
    int fd;
    char *tmpdir;
    int rc;

    rc = get_cmdline_args(argc, argv);
    if (rc) {
        return 104;
    }

    if (options.help) {
        help(argv[0]);
        return 0;
    }

    say("Extracting...\n");
    if (NULL == (tmpdir = make_temp_dir())) {
        rc = 100;
        goto exit;
    }

    if (options.list) {
        if (list(argv[0]) != 0) {
            rc = 105;
            goto exit;
        }
    } else {
        if (untar(argv[0], tmpdir) < 0) {
            rc = 103;
            goto exit;
        }
    }

    if (!options.list)
        rc = run_setup(tmpdir);

exit:
    cleanup(tmpdir);

    return rc;
}
