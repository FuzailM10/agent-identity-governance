"""Vercel entry point.

Vercel's @vercel/python runtime serves the ASGI `app` exposed here. We add the
`engine/` folder to the import path so the existing app code is reused as-is —
no duplication between local and cloud.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))

from app.main import app  # noqa: E402,F401  (Vercel serves this `app`)
