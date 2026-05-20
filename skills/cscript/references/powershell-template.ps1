#!/usr/bin/env pwsh
# NAME: example-name
# DESC: One-line description in present tense, no trailing period
# USAGE: example-name <required-arg> [-Flag]
#
# Replace this header when generating. Keep NAME / DESC / USAGE — `cscript show`
# prints them above the source. The DESC line is what `cscript which` matches.

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Required,

    [switch]$Flag,

    [Alias('h')]
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

function Show-Usage {
    @'
Usage: example-name <required-arg> [-Flag]

Description here.

Args:
  required-arg    What it is

Flags:
  -Flag           What it does
  -h, -Help       Show this help
'@
}

if ($Help) {
    Show-Usage
    exit 0
}

if (-not $Required) {
    [Console]::Error.WriteLine((Show-Usage))
    exit 2
}

# --- implementation below ---
