#!/usr/bin/env python3
"""旧名の CLI と、既存の pages.py の import を保つ。新しい入口は build_slides.py。--selftest も渡す。"""
import runpy
import sys

if __name__ == "__main__":
    runpy.run_module("build_slides", run_name="__main__", alter_sys=True)
else:
    import build_slides
    sys.modules[__name__] = build_slides
