# SPDX-License-Identifier: GPL-3.0-or-later
"""Supported directory-plugin entry point; imports only its shipped relative package."""
from .hermes_outcome_loop import register

__all__ = ["register"]
