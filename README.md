# Single Higgs Combinations (SHI)

Custom tasks for Single Higgs combinations, extending the [HH inference tools](https://gitlab.cern.ch/hh/tools/inference).

## Overview

This repository uses the HH inference tools as a foundation and adds custom tasks for Single Higgs analysis combinations. It maintains all the DHI (Di-Higgs Inference) infrastructure while allowing customization of:

- **Combine version**: Uses v10.3.1 (newer than DHI default v9.1.0)
- **Custom tasks**: Extends DHI tasks with additional functionality
- **Analysis-specific workflows**: Tailored for Single Higgs combinations

> **⚠️ Known Issue**: The inference tool examples and HelloWorld task do not work with Combine v10.3.1 due to segmentation faults in RooFit's compilation system. If you encounter crashes, see the [Using DHI Default Versions](#using-dhi-default-versions) section to switch to the tested v9.1.0.

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

### 1. Clone the Repository

```bash
git clone --recursive <repository-url> SingleHiggsCombinations
cd SingleHiggsCombinations
```

The `--recursive` flag automatically initializes and clones all submodules (including the inference tools).

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

### 3. Index Law Tasks

```bash
law index --verbose
```

This makes law aware of both DHI and SHI tasks for command-line autocompletion.

## Configuration

During the first setup, you'll be prompted for:
- `DHI_USER`: Your CERN/WLCG username
- `DHI_DATA`: Local data directory (default: `./data`)
- `DHI_STORE`: Output store directory
- `DHI_SOFTWARE`: Software installation directory
- And other configuration options

These settings are saved to `.setups/shi_default.sh` for future use.

## Subsequent Usage

After the first setup, simply source the setup script:

```bash
cd SingleHiggsCombinations
source setup.sh
```

This will use your saved configuration from `.setups/shi_default.sh`.

## Combine Version Configuration

### Using DHI Default Versions

This repository is configured to use **Combine v10.3.1** by default, but the inference tool examples were tested with **v9.1.0**. To use the DHI-tested default versions:

```bash
# Remove any custom version settings
unset DHI_COMBINE_VERSION
unset DHI_CMSSW_VERSION
unset DHI_SCRAM_ARCH

# Source setup - this will use inference defaults (v9.1.0)
source setup.sh
```

Alternatively, you can explicitly set the DHI default versions before sourcing:

```bash
export DHI_COMBINE_VERSION=v9.1.0
export DHI_CMSSW_VERSION=CMSSW_14_0_0_pre1
export DHI_SCRAM_ARCH=el9_amd64_gcc12
source setup.sh
```

**Note**: After switching versions, you'll need to reinstall Combine:

```bash
DHI_REINSTALL_COMBINE=1 source setup.sh
```

### Using Custom Combine Version

To use a different version:

```bash
DHI_COMBINE_VERSION=v10.0.0 source setup.sh
```

The setup script will show a warning when using non-default versions.

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

### HZZ Njets likelihood scans
These custom law/luigi tasks under shi.tasks do:

1. build a workspace from an HZZ Run-2 datacard (text2workspace.py, multiSignalModel)
2. create a Combine snapshot (global fit, freeze MH)  
3. run 1D likelihood grid scans for each POI r_Njets_[0..4]    
4. merge scan outputs into .npz    
5. make per-POI 1D likelihood plots (nll1d__...pdf/png)    
6. produce a final Njets “step” XS plot comparing HZZ result vs theory from your .pkl files

**How to run**

0) Setup environment (as you already do)
```bash
cd SingleHiggsCombinations
source setup.sh
```
1) Quick sanity check
   
Make sure law “sees” the tasks:
```bash
law index --verbose
law index | grep -E "shi\.HZZ(AllPOIs|PlotNjetsXS|LikelihoodScan|MergeLikelihoodScan|PlotLikelihoodScan)" -n
```

2) Run the full chain for all Njets POIs

Workspace → snapshot → scans → merges → 1D likelihood plots:

```bash
law run shi.HZZAllPOIs
```

3) Build the final Njets “step” XS plot (HZZ vs theory)

This task consumes the merged .npz outputs + your theory .pkl files:

```bash
law run shi.HZZPlotNjetsXS 
```
**Inputs you must set**
1) Pass your own datacard path (or keep the default if you already set it in the task):

        --datacards /path/to/your/hzz_datacard.txt
2) Theory .pkl files

Provide your own AFS paths (don’t copy someone else’s):

- theory_pred_pkl: numpy array shape [5,3]
- theory_unc_pkl: numpy array shape [2,5]
  
**Paths you must change**

- These defaults are currently hardcoded in shi/tasks/hzz_incremental.py and are very likely personal:

    - Datacard path (HZZBase.datacards default):

        Replace /afs/cern.ch/user/<YOU>/251107_Hzz/hig-21-009/... with yours.

Or override from CLI:
```bash
law run shi.HZZAllPOIs \
  --datacards /path/to/your/hzz_datacard.txt \
  --workspace-name HZZ.root \
  --version dev
```
```bash
law run shi.HZZPlotNjetsXS \
  --version dev \
  --theory-pred-pkl /afs/cern.ch/user/<YOU>/theoryPred_Njets2p5_18_fullPS.pkl \
  --theory-unc-pkl  /afs/cern.ch/user/<YOU>/theoryPred_Njets2p5_18_fullPS_theoryUnc.pkl
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
