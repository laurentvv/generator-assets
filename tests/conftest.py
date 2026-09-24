#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configuration pytest : rend le répertoire du projet importable (main, core, workflows)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
