#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PARENT_DIR}/.venv"
ACTIVATE_SCRIPT="${VENV_DIR}/bin/activate"
PYTHON_SCRIPT="${VENV_DIR}/bin/python3"

source ${ACTIVATE_SCRIPT}
MPLCONFIGDIR=/tmp/mpl_config ${PYTHON_SCRIPT} ${SCRIPT_DIR}/generate_charts.py
deactivate