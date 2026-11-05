"""
Build and describe Python API reference content

`exports` reuses package models and discovered exports within a build. `discovery` finds
exports and categorises them. `probe` checks whether objects can be documented and detects
configuration defaults. `sections` builds section descriptions, and `block` writes the Quarto
reference settings and navigation. `documented` lists what the reference documents without
building the site.
"""
