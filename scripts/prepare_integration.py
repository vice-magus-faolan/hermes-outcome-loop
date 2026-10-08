#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Retired host preparer. Preserved partial output is historical evidence only.

The Docker recovery decision supersedes this path. This command cannot create,
copy, restart or delete the interrupted host environment.
"""
import sys


def main():
    print("ERROR: host preparation retired; use the budgeted public Docker provisioning phase "
          "and scripts/verify.py with HERMES_OUTCOME_IMAGE. Preserved partial output is untouched.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
