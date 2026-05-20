@echo off
rem Windows wrapper for the cscript dispatcher.
rem Install BOTH this file and the extensionless `cscript` source into the
rem same directory on PATH. Windows resolves cscript.cmd via PATHEXT; this
rem then hands the PEP 723 source to `uv run --script`.
uv run --script "%~dp0cscript" %*
