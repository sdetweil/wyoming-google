#!/usr/bin/env bash
set -eo pipefail

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"

# Base directory of repo
base_dir="$(realpath "${this_dir}/..")"

# Path to virtual environment
: "${venv:=${base_dir}/.venv}"

if [ -d "${venv}" ]; then
    source "${venv}/bin/activate"
fi
cd test
python3 "${base_dir}/test/wav2text.py" "$@"
