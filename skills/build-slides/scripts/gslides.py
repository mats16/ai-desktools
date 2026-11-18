#!/usr/bin/env python3
"""旧名の CLI と import を保つ。新しい入口は check_slides.py。--selftest も渡す。"""
import runpy
import sys

if __name__ == "__main__":
    runpy.run_module("check_slides", run_name="__main__", alter_sys=True)
else:
    import check_slides
    sys.modules[__name__] = check_slides
