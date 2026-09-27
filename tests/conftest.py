#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pytest configuration: makes the project directory importable (main, core, workflows)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
