"""
Documentation build support

The bodies of build steps are module functions in modules grouped by what they do, such as
`render` and `finish`. A step function takes the current `Run` first when it reads per-build
values, then the configuration and layout, then the build log, then its own values, and
returns an `Outcome`. A step that also hands a value to a later step returns it beside its
outcome or result.
"""
