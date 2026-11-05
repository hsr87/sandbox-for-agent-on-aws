// Micro-benchmarks that bypass the Python interpreter, so that the same binary
// measures the kernel interface of each sandbox. Prints one JSON line of ns/op.
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static double now(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return t.tv_sec * 1e9 + t.tv_nsec;
}
#define RUN(label, n, body)                 \
  do {                                      \
    double s = now();                       \
    for (long i = 0; i < (n); i++) { body; }\
    printf("\"%s\":%.1f,", label, (now() - s) / (n)); \
  } while (0)

int main(void) {
  const char *path = "/tmp/.sb";
  int fd = open(path, O_CREAT | O_RDWR, 0600);
  close(fd);
  char buf[1];
  int p1[2], p2[2];
  printf("{");
  RUN("getppid_ns", 1000000L, syscall(SYS_getppid));
  RUN("clock_gettime_ns", 2000000L, { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); });
  RUN("open_close_ns", 100000L, { int f = open(path, O_RDONLY); close(f); });
  long pg = sysconf(_SC_PAGESIZE);
  RUN("page_fault_ns", 100L, {
    size_t len = 4096 * pg;
    char *m = mmap(NULL, len, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    for (size_t j = 0; j < len; j += pg) m[j] = 1;
    munmap(m, len);
  });
  if (pipe(p1) == 0 && pipe(p2) == 0) {
    pid_t c = fork();
    if (c == 0) {
      close(p1[1]);
      close(p2[0]);
      while (read(p1[0], buf, 1) == 1) { if (write(p2[1], buf, 1) != 1) break; }
      _exit(0);
    }
    RUN("pipe_roundtrip_ns", 50000L, {
      if (write(p1[1], "x", 1) != 1 || read(p2[0], buf, 1) != 1) break;
    });
    close(p1[1]);
    waitpid(c, NULL, 0);
  }
  RUN("fork_exit_ns", 1000L, { pid_t c = fork(); if (c == 0) _exit(0); waitpid(c, NULL, 0); });
  RUN("fork_exec_ns", 500L, {
    pid_t c = fork();
    if (c == 0) { execl("/bin/true", "true", (char *)NULL); _exit(1); }
    waitpid(c, NULL, 0);
  });
  unlink(path);
  printf("\"ok\":1}\n");
  return 0;
}
