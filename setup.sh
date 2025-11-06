#!/usr/bin/env bash

setup() {
    #
    # Prepare local variables
    #

    local this_file="$( [ ! -z "${ZSH_VERSION}" ] && echo "${(%):-%x}" || echo "${BASH_SOURCE[0]}" )"
    local this_dir="$( cd "$( dirname "${this_file}" )" && pwd )"
    local orig="${PWD}"
    local setup_name="${1:-shi_default}"


    #
    # Export base directory
    #

    export SHI_BASE="${this_dir}"
    echo "Single Higgs Combinations base: ${SHI_BASE}"


    #
    # Override Combine and CMSSW versions BEFORE sourcing inference setup
    #

    export DHI_COMBINE_VERSION="${DHI_COMBINE_VERSION:-v10.3.1}"
    export DHI_CMSSW_VERSION="${DHI_CMSSW_VERSION:-CMSSW_14_1_0_pre4}"
    export DHI_SCRAM_ARCH="${DHI_SCRAM_ARCH:-el9_amd64_gcc12}"

    echo "Using Combine ${DHI_COMBINE_VERSION} with ${DHI_CMSSW_VERSION}"

    # Warn if using non-tested Combine version
    if [[ "${DHI_COMBINE_VERSION}" != "v9.1.0" ]]; then
        >&2 echo ""
        >&2 echo "WARNING: Using Combine ${DHI_COMBINE_VERSION} instead of DHI-tested v9.1.0"
        >&2 echo "         Some DHI tasks might not work correctly with this version."
        >&2 echo "         Proceeding with custom Combine version..."
        >&2 echo ""
    fi


    #
    # Source the inference setup
    #

    if [ ! -f "${SHI_BASE}/inference/setup.sh" ]; then
        >&2 echo "ERROR: inference/setup.sh not found!"
        >&2 echo "       Please ensure the inference submodule is initialized:"
        >&2 echo "       git submodule update --init --recursive"
        return 1
    fi

    # Mark that we're using custom setup
    export SHI_CUSTOM_SETUP="1"

    # Source inference setup with the same setup name
    source "${SHI_BASE}/inference/setup.sh" "${setup_name}" || return "$?"


    #
    # Add SHI module to Python path
    #

    local pyv="$( python3 -c "import sys; print('{0.major}.{0.minor}'.format(sys.version_info))" )"
    export PYTHONPATH="${SHI_BASE}:${PYTHONPATH}"

    # Update PATH for custom scripts if needed
    export PATH="${SHI_BASE}/bin:${PATH}"


    #
    # Store setup name
    #

    export SHI_SETUP_NAME="${setup_name}"


    #
    # Law setup for SHI tasks
    #

    if which law &> /dev/null; then
        # Re-index to include SHI tasks
        law index -q
    fi

    cd "${orig}"
}

action() {
    if setup "$@"; then
        echo -e "\x1b[0;49;35mSingle Higgs Combination tools successfully setup\x1b[0m"
        echo "  - Combine version: ${DHI_COMBINE_VERSION}"
        echo "  - CMSSW version: ${DHI_CMSSW_VERSION}"
        echo "  - Setup name: ${SHI_SETUP_NAME}"
        echo "  - SHI tasks available in 'shi.tasks'"
        return "0"
    else
        local code="$?"
        echo -e "\x1b[0;49;31msetup failed with code ${code}\x1b[0m"
        return "${code}"
    fi
}

action "$@"
