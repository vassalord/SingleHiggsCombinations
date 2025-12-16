# shi/tasks/hzz_incremental.py
# coding: utf-8

import law
import luigi

import os
import pickle
import numpy as np
import matplotlib.pyplot as plt
import mplhep as hep

from law.util import flatten
# DHI building blocks
from dhi.tasks.combine import (
    CreateWorkspace as DhiCreateWorkspace,
    POITask,
)
from dhi.tasks.snapshot import Snapshot as DhiSnapshot
from dhi.config import poi_data
from dhi.tasks.likelihoods import (
    LikelihoodScan as DhiLikelihoodScan,
    MergeLikelihoodScan as DhiMergeLikelihoodScan,
    PlotLikelihoodScan as DhiPlotLikelihoodScan,
    PlotMultipleLikelihoodScans as DhiPlotMultipleLikelihoodScans,
)

import law.parameter as law_parameter
from law.target.local import LocalFileTarget
from dhi.tasks.combine import CombineDatacards
from law.util import create_hash
from law.target.local import LocalFileTarget

# ---------------------------------------------------------------------------
# Force keep_additional_signals = "all" for all tasks using CombineDatacards
# ---------------------------------------------------------------------------

try:
    old_param = CombineDatacards.keep_additional_signals

    CombineDatacards.keep_additional_signals = luigi.ChoiceParameter(
        default="all",
        choices=list(old_param.choices),   # ["no", "all", "sh"]
        significant=old_param.significant,
        description=old_param.description,
    )
except Exception:
    pass

class HZZPOIEntry(dict):
    def __init__(self, label, sm_value=1.0):
        super().__init__(label=label, sm_value=sm_value)
        self.label = label
        self.sm_value = sm_value


_hzz_njets_pois = tuple(f"r_Njets_{i}" for i in range(5))

for i, name in enumerate(_hzz_njets_pois):
    if name not in poi_data:
        label = f"r_{{N_{{\\text{{jets}}={i}}}}}"
        poi_data[name] = HZZPOIEntry(label=label, sm_value=1.0)

try:
    poi_choices = getattr(POITask.poi, "choices", None)
    if poi_choices is not None:
        POITask.poi.choices = tuple(list(poi_choices) + list(_hzz_njets_pois))
except Exception:
    pass

try:
    pois_choices = getattr(POITask.pois, "choices", None)
    if pois_choices is not None:
        POITask.pois.choices = tuple(list(pois_choices) + list(_hzz_njets_pois))
except Exception:
    pass



# ---------------------------------------------------------------------------
# Base task (version, datacards path, workspace name)
# ---------------------------------------------------------------------------

class HZZBase(law.Task):
    task_namespace = "shi"

    # DHI expects a version; keep it user-settable from CLI
    version = luigi.Parameter(default="dev", description="analysis version tag")

    # Default HZZ Run-2 datacard (can be overridden on CLI)
    datacards = law.CSVParameter(
        default=(
            "/afs/cern.ch/user/s/shoienko/251107_Hzz/hig-21-009/"
            "njets_pt30_eta4p7/hzz4l_all_13TeV_xs_njets_pt30_eta4p7_bin_v3.txt",
        ),
        description="one or more datacards; CSV or glob patterns allowed",
    )

    # Name for the produced workspace file
    workspace_name = luigi.Parameter(default="HZZ.root")

    hh_model = luigi.Parameter(
        default=law.NO_STR, 
        description="HH model is irrelevant for single-Higgs HZZ; leave empty.",
    )


    # DHI Combine tasks accept an empty hh_model when this flag is True
    allow_empty_hh_model = True


# ---------------------------------------------------------------------------
# Small mixins to relax DHI's POI checks and inject our Njets POIs
# ---------------------------------------------------------------------------

class AnyPOIsMixin(law.Task):
    # CSV of POIs without choices restriction
    pois = law.CSVParameter(
        default=(),
        description="free-form POI names",
    )

    poi = law.Parameter(
        default="r_Njets_0",
        description="single free-form POI name",
    )


class HZZPOIMixin(law.Task):

    def load_model_pois(self):
        self._r_pois = (
            "r_Njets_0",
            "r_Njets_1",
            "r_Njets_2",
            "r_Njets_3",
            "r_Njets_4",
        )
        self._k_pois = tuple()

    def get_output_postfix_pois(self):
        return tuple()

    @property
    def joined_parameter_values(self):
        pvals = getattr(self, "parameter_values", "")
        if not pvals:
            return '""'
        parts = []
        for name, val in pvals:
            parts.append(f"{name}={val}")
        return ",".join(parts)
    def get_shown_parameters(self):
        return {}

# ---------------------------------------------------------------------------
# 1) CreateWorkspace: text2workspace with multiSignalModel mapping for r_Njets_i
# ---------------------------------------------------------------------------

class HZZCreateWorkspace(HZZBase, DhiCreateWorkspace):
    mass = luigi.FloatParameter(default=125.38)

    def output(self):
        """
        Final workspace path (law target).
        """
        return self.target(self.workspace_name)

    def build_command(self, fallback_level):
        datacard = self.datacards[0] if self.no_bundle else self.input().path

        cmd = (
            "text2workspace.py {dc} "
            "-o workspace.root "
            "-P HiggsAnalysis.CombinedLimit.PhysicsModel:multiSignalModel "
            "--for-fits --no-wrappers --X-pack-asympows --optimize-simpdf-constraints=cms "
            "--PO 'higgsMassRange=123,127' "
            "--PO 'map=.*/smH_NJ_0p0_1p0:r_Njets_0[1.0,0.0,3.0]' "
            "--PO 'map=.*/smH_NJ_1p0_2p0:r_Njets_1[1.0,0.0,3.0]' "
            "--PO 'map=.*/smH_NJ_2p0_3p0:r_Njets_2[1.0,0.0,3.0]' "
            "--PO 'map=.*/smH_NJ_3p0_4p0:r_Njets_3[1.0,0.0,3.0]' "
            "--PO 'map=.*/smH_NJ_4p0_14p0:r_Njets_4[1.0,0.0,3.0]' "
            "-m {mass} "
            "&& mv workspace.root {out}"
        ).format(dc=datacard, mass=self.mass, out=self.output().path)
        return cmd


# ---------------------------------------------------------------------------
# 2) Snapshot: do a global fit, freeze MH, store as Combine snapshot for scans
# ---------------------------------------------------------------------------

class HZZSnapshot(HZZBase, AnyPOIsMixin, HZZPOIMixin, DhiSnapshot):

    allow_empty_hh_model = True

    def workflow_requires(self):
        reqs = super(HZZSnapshot, self).workflow_requires()
        reqs["workspace"] = HZZCreateWorkspace.req_different_branching(self)
        return reqs

    def requires(self):
        return HZZCreateWorkspace.req(self, branch=0)

    def build_command(self, fallback_level):
        workspace = self.input().path
        output = self.output().path
        seed = self.branch if getattr(self, "branch", -1) >= 0 else 0

        cmd = (
            "combine --method MultiDimFit {workspace}"
            " --verbose 1"
            " --mass {mass}"
            " --seed {seed}"
            " --algo none"
            " --freezeParameters MH"
            " --floatOtherPOIs 1"
            " --saveWorkspace"
            " --saveNLL"
            " --cminDefaultMinimizerStrategy 0"
            " && "
            "mv higgsCombineTest.MultiDimFit.mH*.root {output}"
        ).format(
            workspace=workspace,
            mass=self.mass,
            seed=seed,
            output=output,
        )

        return cmd


# ---------------------------------------------------------------------------
# 3) LikelihoodScan: 1D grid scan for a single POI r_Njets_i
# ---------------------------------------------------------------------------

class HZZLikelihoodScan(
    HZZBase,
    AnyPOIsMixin,
    HZZPOIMixin,
    DhiLikelihoodScan,
):

    use_snapshot = True
    mass = luigi.FloatParameter(default=125.38)

    custom_args = luigi.Parameter(
        default="--floatOtherPOIs=1 --cminDefaultMinimizerStrategy 0 --freezeParameters MH",
        significant=False,
        description="extra args passed to combine",
    )

    @classmethod
    def modify_param_values(cls, params):
        params = super(HZZLikelihoodScan, cls).modify_param_values(params)

        poi = params.get("poi", "r_Njets_0")

        params["pois"] = (poi,)
        params["scan_parameters"] = ((poi, 0.0, 2.0, 200),)

        all_pois = [f"r_Njets_{i}" for i in range(5)]
        others = [p for p in all_pois if p != poi]

        pvals = list(params.get("parameter_values", ()))
        pvals = [pv for pv in pvals if pv[0] not in all_pois]
        for op in others:
            pvals.append((op, "1"))
        params["parameter_values"] = tuple(pvals)

        frozen = list(params.get("frozen_parameters", ()))
        if "MH" not in frozen:
            frozen.append("MH")
        params["frozen_parameters"] = tuple(frozen)

        return params

    def workflow_requires(self):

        reqs = {}

        if self.use_snapshot:
            reqs["snapshot"] = HZZSnapshot.req_different_branching(self)
        else:
            reqs["workspace"] = HZZCreateWorkspace.req_different_branching(self)

        return reqs

    def requires(self):
        if self.use_snapshot:
            return {
                "snapshot": HZZSnapshot.req(self),
            }

        return super(HZZLikelihoodScan, self).requires()


# ---------------------------------------------------------------------------
# 4) MergeLikelihoodScan: merge grid branches of a scan
# ---------------------------------------------------------------------------

class HZZMergeLikelihoodScan(
    HZZBase,
    AnyPOIsMixin,
    HZZPOIMixin,
    DhiMergeLikelihoodScan,
):

    def requires(self):
        return HZZLikelihoodScan.req(self)
    @classmethod
    def modify_param_values(cls, params):
        params = super(HZZMergeLikelihoodScan, cls).modify_param_values(params)
        poi = params.get("poi", "r_Njets_0")
        params["pois"] = (poi,)
        params["scan_parameters"] = ((poi, 0.0, 2.0, 200),)
        return params


# ---------------------------------------------------------------------------
# 5) PlotLikelihoodScan: draw the 1D likelihood curve
# ---------------------------------------------------------------------------

class HZZPlotLikelihoodScan(
    HZZBase,
    AnyPOIsMixin,
    HZZPOIMixin,
    DhiPlotLikelihoodScan,
):

    def get_axis_limit(self, name):
        if name == "x_min":
            return 0.0
        if name == "x_max":
            return 2.0

        if name == "y_min":
            return 0.0
        if name == "y_max":
            return 10.0
    def requires(self):
        return [HZZMergeLikelihoodScan.req(self)]

    @classmethod
    def modify_param_values(cls, params):
        params = super(HZZPlotLikelihoodScan, cls).modify_param_values(params)
        poi = params.get("poi", "r_Njets_0")
        params["pois"] = (poi,)
        params["scan_parameters"] = ((poi, 0.0, 2.0, 200),)
        return params


# ---------------------------------------------------------------------------
# 6) PlotMultipleLikelihoodScans: overlay multiple POIs on one canvas
# ---------------------------------------------------------------------------

class HZZPlotMultipleLikelihoodScans(
    HZZBase,
    AnyPOIsMixin,    # allow free-form POI names
    HZZPOIMixin,     # pretend the model has r_Njets_[0..4] as POIs
    DhiPlotMultipleLikelihoodScans,
):

    def get_axis_limit(self, name):
        if name == "x_min":
            return 0.0
        if name == "x_max":
            return 2.0

        if name == "y_min":
            return 0.0
        if name == "y_max":
            return 10.0
    pois = law.CSVParameter(
        default=("r_Njets_0",),
        description="POIs to overlay",
    )

    @classmethod
    def modify_param_values(cls, params):
        params = super(HZZPlotMultipleLikelihoodScans, cls).modify_param_values(params)

        pois = params.get("pois") or ("r_Njets_0",)
        poi = pois[0]
        params["pois"] = (poi,)

        # Keep the same scan definition as in HZZLikelihoodScan / HZZMergeLikelihoodScan
        params["scan_parameters"] = ((poi, 0.0, 2.0, 200),)

        return params

    def requires(self):

        requirements = []
        for datacard_group in self.multi_datacards:
            merge_tasks = [
                HZZMergeLikelihoodScan(
                    version=self.version,
                    datacards=tuple(datacard_group),
                    workspace_name=self.workspace_name,
                    poi=self.pois[0],
                )
            ]
            requirements.append(merge_tasks)

        return requirements

# ---------------------------------------------------------------------------
# 7) HZZAllPOIs: orchestrate full chain for the 5 Njets POIs
# ---------------------------------------------------------------------------
class HZZAllPOIs(HZZBase, law.WrapperTask):
    def requires(self):
        ws = HZZCreateWorkspace(
            version=self.version,
            datacards=self.datacards,
            workspace_name=self.workspace_name,
        )
        snap = HZZSnapshot(
            version=self.version,
            datacards=self.datacards,
            workspace_name=self.workspace_name,
        )

        pois = [f"r_Njets_{i}" for i in range(5)]

        scans = [
            HZZLikelihoodScan(
                version=self.version,
                datacards=self.datacards,
                workspace_name=self.workspace_name,
                poi=p,
            )
            for p in pois
        ]

        merges = [
            HZZMergeLikelihoodScan(
                version=self.version,
                datacards=self.datacards,
                workspace_name=self.workspace_name,
                poi=p,
            )
            for p in pois
        ]

        plots = [
            HZZPlotLikelihoodScan(
                version=self.version,
                datacards=self.datacards,
                workspace_name=self.workspace_name,
                poi=p,
            )
            for p in pois
        ]

        return {
            "workspace": ws,
            "snapshot": snap,
            "scans": scans,
            "merges": merges,
            "plots": plots,
        }


# ---------------------------------------------------------------------------
# 8) HZZPlotNjetsXS: final "step" plot using merged scan results + theory pkls
# ---------------------------------------------------------------------------
class HZZPlotNjetsXS(HZZBase):
    """
    Build the final Njets step-plot from:
      - MergeLikelihoodScan outputs for r_Njets_0..4  (npz)
      - theory prediction pkl:    (5,3)
      - theory uncertainty pkl:   (2,5)

    Output is written under:
      <repo>/data/plots/njets_xs/datacards_<hash>/v<version>/
    """

    pois = law.CSVParameter(
        default=tuple(f"r_Njets_{i}" for i in range(5)),
        description="POIs to use (expected r_Njets_0..4).",
    )

    theory_pred_pkl = luigi.Parameter(
        default="/afs/cern.ch/user/s/shoienko/theoryPred_Njets2p5_18_fullPS.pkl",
        description="Path to theory prediction pkl (numpy array shape [5,3]).",
    )

    theory_unc_pkl = luigi.Parameter(
        default="/afs/cern.ch/user/s/shoienko/theoryPred_Njets2p5_18_fullPS_theoryUnc.pkl",
        description="Path to theory uncertainty pkl (numpy array shape [2,5]).",
    )

    def requires(self):
        # One merged scan per POI
        reqs = {}
        for p in self.pois:
            reqs[p] = HZZMergeLikelihoodScan.req(self, poi=p)
        return reqs

    def output(self):
        # hash datacards so different inputs don't overwrite each other
        dc_hash = create_hash(tuple(self.datacards))

        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        out_base = os.path.join(
            repo_root,
            "data",
            "plots",
            "njets_xs",
            f"datacards_{dc_hash}",
            f"v{self.version}",
        )

        return {
            "json": LocalFileTarget(os.path.join(out_base, f"njets_xs__{self.version}.json")),
            "pdf":  LocalFileTarget(os.path.join(out_base, f"njets_xs__{self.version}.pdf")),
            "png":  LocalFileTarget(os.path.join(out_base, f"njets_xs__{self.version}.png")),
        }

    @law.decorator.log
    @law.decorator.safe_output
    def run(self):
        from shi.plots.njets_xs import plot_njets_xs

        out = self.output()

        # Ensure output directory exists (so complete()/run() never fails on mkdir)
        os.makedirs(os.path.dirname(out["pdf"].path), exist_ok=True)

        merge_npz_by_poi = {poi: tgt.path for poi, tgt in self.input().items()}

        plot_njets_xs(
            merge_npz_by_poi=merge_npz_by_poi,
            theory_pred_pkl=self.theory_pred_pkl,
            theory_unc_pkl=self.theory_unc_pkl,
            out_pdf=out["pdf"].path,
            out_png=out["png"].path,
            out_json=out["json"].path,
            title="HZZ",
            cms_label="Preliminary",
            lumi_fb=None,
        )