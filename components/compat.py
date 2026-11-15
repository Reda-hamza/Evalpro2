"""Compatibilité entre versions de Streamlit.

Les versions récentes (>= 1.52) utilisent width="stretch" ; les anciennes n'acceptent que
use_container_width=True. `STRETCH` s'utilise ainsi : st.button("OK", **STRETCH).
"""
import re

import streamlit as st


def _version() -> tuple[int, int]:
    nums = re.findall(r"\d+", st.__version__)
    return int(nums[0]), int(nums[1]) if len(nums) > 1 else 0


STRETCH: dict = {"width": "stretch"} if _version() >= (1, 52) else {"use_container_width": True}
