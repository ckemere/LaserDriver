/*
 * Build-time version string.  The Makefiles pass -DFW_VERSION="..." (from
 * `git describe --tags --always --dirty`, with the leading "v" dropped and
 * "-" turned into "+", matching the Debian package version), and rebuild
 * this one file on every make so the string can never go stale.  A build
 * without the define (no git, hand-run compiler) reports "unversioned".
 */
#include "version.h"

#ifndef FW_VERSION
#define FW_VERSION "unversioned"
#endif

const char fw_version[] = FW_VERSION;
