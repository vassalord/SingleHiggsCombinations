# Single Higgs Combinations (SHI)

Custom tasks for Single Higgs combinations, extending the [HH inference tools](https://gitlab.cern.ch/hh/tools/inference).

## Overview

This repository uses the HH inference tools as a foundation and adds custom tasks for Single Higgs analysis combinations. It maintains all the DHI (Di-Higgs Inference) infrastructure while allowing customization of:

- **Combine version**: Uses v10.3.1 (newer than DHI default v9.1.0)
- **Custom tasks**: Extends DHI tasks with additional functionality
- **Analysis-specific workflows**: Tailored for Single Higgs combinations

## Repository Structure

```
SingleHiggsCombinations/
├── inference/              # HH inference tools (submodule)
│   ├── dhi/               # DHI tasks and utilities
│   ├── modules/           # law and plotlib submodules
│   └── setup.sh           # DHI setup script
├── shi/                   # Single Higgs Combinations package
│   ├── __init__.py
│   └── tasks/             # Custom SHI tasks
│       ├── __init__.py
│       └── hello_world.py # Example task extending DHI
├── bin/                   # Custom scripts (optional)
├── .setups/               # Setup configurations
├── setup.sh               # Main setup script (wraps inference/setup.sh)
├── law.cfg                # Law configuration (extends inference/law.cfg)
└── README.md              # This file
```

## First-Time Setup

### 1. Initialize Git and Submodules

If you just cloned this repository (or will clone it later):

```bash
cd SingleHiggsCombinations

# If you're setting this up as a git repo for the first time:
git init
git add .
git commit -m "Initial commit"

# Convert inference to a proper submodule:
rm -rf inference
git submodule add ssh://git@gitlab.cern.ch:7999/hh/tools/inference.git inference
git submodule update --init --recursive
```

**Note**: The `inference` directory is currently cloned as a regular directory. When you initialize git, you should convert it to a proper submodule using the commands above.

### 2. Source the Setup Script

```bash
source setup.sh
```

On first run, this will:
- Install Combine v10.3.1 and CMSSW_14_1_0_pre4
- Install the DHI software stack
- Initialize the law and plotlib submodules
- Prompt you for configuration (default setup name: `shi_default`)

**Important**: The setup process may take 15-30 minutes on first run due to CMSSW compilation.

### 3. Configure Your Setup

You'll be prompted for:
- `DHI_USER`: Your CERN/WLCG username
- `DHI_DATA`: Local data directory (default: `./data`)
- `DHI_STORE`: Output store directory
- `DHI_SOFTWARE`: Software installation directory
- And other configuration options

These settings are saved to `.setups/shi_default.sh` for future use.

### 4. Index Law Tasks

```bash
law index --verbose
```

This makes law aware of both DHI and SHI tasks for command-line autocompletion.

## Subsequent Usage

After the first setup, simply source the setup script:

```bash
cd SingleHiggsCombinations
source setup.sh
```

This will use your saved configuration from `.setups/shi_default.sh`.

## Using Custom Combine Version

This repository uses **Combine v10.3.1** instead of the DHI default (v9.1.0). The setup script will show a warning about this.

To use a different version:

```bash
DHI_COMBINE_VERSION=v10.0.0 source setup.sh
```

## Available Tasks

### DHI Tasks

All tasks from the HH inference tools are available:

```bash
law run --help                    # List all tasks
law run PlotUpperLimits --help    # DHI upper limits task
law run PlotLikelihoodScan --help # DHI likelihood scan task
# ... and many more
```

See the [DHI documentation](https://cms-hh.web.cern.ch/cms-hh/tools/inference/index.html) for details.

### SHI Tasks

Custom tasks in the `shi.tasks` namespace:

```bash
law run shi.HelloWorld --help     # Example task extending DHI
```

## Example: Hello World Task

The `HelloWorld` task demonstrates how to extend DHI tasks:

```bash
law run shi.HelloWorld \
    --version dev \
    --datacards $DHI_EXAMPLE_CARDS \
    --custom-message "My custom analysis!" \
    --xsec fb \
    --y-log
```

This task:
- Extends `dhi.tasks.limits.PlotUpperLimits`
- Adds custom printouts before/after running
- Accepts all PlotUpperLimits parameters plus a custom message

## Creating New SHI Tasks

To create a new custom task:

1. **Create a new file** in `shi/tasks/`:

```python
# shi/tasks/my_task.py
import law
import luigi
from dhi.tasks.base import AnalysisTask

class MyTask(AnalysisTask):
    task_namespace = "shi"

    my_param = luigi.Parameter(
        default="default_value",
        description="my custom parameter"
    )

    def run(self):
        # Your custom logic
        pass
```

2. **Add to `shi/tasks/__init__.py`**:

```python
__all__ = [
    "HelloWorld",
    "MyTask",  # Add your task
]

from shi.tasks.hello_world import HelloWorld
from shi.tasks.my_task import MyTask  # Import it
```

3. **Re-index**:

```bash
law index --verbose
```

4. **Run your task**:

```bash
law run shi.MyTask --help
```

## Updating the Inference Submodule

To update to a newer version of the inference tools:

```bash
cd inference
git fetch origin
git checkout master  # or specific tag/commit
git pull
cd ..
git add inference
git commit -m "Update inference submodule"
```

## Environment Variables

Key environment variables set by the setup:

- `SHI_BASE`: Base directory of this repository
- `DHI_BASE`: Base directory of inference submodule
- `DHI_COMBINE_VERSION`: Combine version (v10.3.1)
- `DHI_CMSSW_VERSION`: CMSSW version (CMSSW_14_1_0_pre4)
- `DHI_DATA`: Data directory
- `DHI_STORE`: Output store directory
- `DHI_SOFTWARE`: Software installation directory

## Troubleshooting

### "inference/setup.sh not found"

Make sure the inference submodule is initialized:

```bash
git submodule update --init --recursive
```

### Combine installation fails

Try reinstalling:

```bash
DHI_REINSTALL_COMBINE=1 source setup.sh
```

### Law can't find SHI tasks

Re-index:

```bash
law index --verbose
```

### Setup configuration questions every time

Make sure you're using the same setup name:

```bash
source setup.sh shi_default
```

## Documentation

- [DHI Tasks Documentation](https://cms-hh.web.cern.ch/cms-hh/tools/inference/index.html)
- [Law Framework](https://law.readthedocs.io/)
- [Combine Tool](https://cms-analysis.github.io/HiggsAnalysis-CombinedLimit/)

## Contact

For questions about this repository, contact Massimiliano Galli.

For questions about the DHI tools, see the [inference repository](https://gitlab.cern.ch/hh/tools/inference).
