
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include "libtar.h"

#define THIS_FILE_SIZE   0

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

static char * make_temp_dir()
{
    pid_t pid = getpid();
    char *tmpdir = getenv("TMP");
    char *td;
    int err;

    if (NULL == tmpdir) {
        tmpdir = "/tmp";
    }

    td = fstring("%s/selfex__%d", tmpdir, pid);
    err = mkdir(td, 0700);
    if (err < 0) {
        fprintf(stderr, "Couldn't create temporary directory.\n");
        fprintf(stderr, "\t[%d] %s\n", errno, strerror(errno));
        return NULL;
    }

    return td;
}


static int untar(int fd, char *tmpdir)
{
    TAR *t;
    int rc;

    fprintf(stdout, "Opening archive %d\n", fd);
    // rc = tar_fdopen(&t, fd, "_tmp.tgz", NULL, O_RDONLY, 0600, TAR_VERBOSE);
    rc = tar_fdopen(&t, fd, "embedded.tar", NULL, O_RDONLY, 0, TAR_VERBOSE | TAR_GNU);// | TAR_IGNORE_CRC );
    if (rc < 0) {
        fprintf(stderr, "Cannot read tar file [%d] %s\n", errno, strerror(errno));
        return rc;
    }

    fprintf(stdout, "Extracting from tar into '%s'\n", tmpdir);
    rc = tar_extract_all(t, tmpdir);
    if (rc < 0) {
        fprintf(stderr, "Error extracting tar file [%d] %s\n", errno, strerror(errno));
        return rc;
    }

    tar_close(t);

    return 0;
}

static int run_setup(char *tmpdir)
{
    int rc;
    char *cmd = fstring("%s/setup %s", tmpdir, tmpdir);
    fprintf(stdout, "running '%s'\n", cmd);
    rc = system(cmd);
    if (rc == -1) {
        fprintf(stderr, "Couldn't run setup [%d] %s\n", errno, strerror(errno));
    } else if (rc > 0) {
        fprintf(stderr, "Command setup failed rc = %d\n", rc);
    }
    return rc;
}

static void cleanup(char *tmpdir)
{
    fprintf(stdout, "Cleaning up %s\n", tmpdir);
}

int main(int argc, char *argv[])
{
    int fd;
    char *tmpdir;
    int rc;

    fprintf(stdout, "Extracting...\n");
    if (NULL == (tmpdir = make_temp_dir())) {
        rc = 100;
        goto exit;
    }

    if ((fd = open(argv[0], O_RDONLY)) < 0) {
        fprintf(stderr, "Couldn't open '%s': [%d] %s\n", argv[0], errno, strerror(errno));
        rc = 101;
        goto exit;
    }

    fprintf(stdout, "Setting position at %d\n", THIS_FILE_SIZE);
    if (lseek(fd, THIS_FILE_SIZE, SEEK_SET) < 0) {
        fprintf(stderr, "Error seeking [%d] %s\n", errno, strerror(errno));
        rc = 102;
        goto exit;
    }

    if (untar(fd, tmpdir) < 0) {
        rc = 103;
        goto exit;
    }

    rc = run_setup(tmpdir);

exit:
    cleanup(tmpdir);

    return rc;
}
