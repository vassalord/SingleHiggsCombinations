# shi/tasks/hzz_incremental.py
# coding: utf-8

import law
import luigi


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

if hasattr(law_parameter.Parameter, "_check_choices"):
    _original_check_choices = law_parameter.Parameter._check_choices

    def _njets_friendly_check_choices(self, value):

        def is_njets(v):
            return isinstance(v, str) and v.startswith("r_Njets_")

        if isinstance(value, (list, tuple, set)):
            vals = list(value)
            if vals and all(is_njets(v) for v in vals):
                return

        if is_njets(value):
            return

        return _original_check_choices(self, value)

    law_parameter.Parameter._check_choices = _njets_friendly_check_choices

from dhi.tasks.combine import CombineDatacards

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


_hzz_njets_pois = tuple(f"r_Njets_{i}" for i in range(5))

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
        # Five POIs used in the HZZ multiSignalModel mapping
        self._r_pois = (
            "r_Njets_0",
            "r_Njets_1",
            "r_Njets_2",
            "r_Njets_3",
            "r_Njets_4",
        )
        # No "kappa"-type POIs here
        self._k_pois = tuple()

    def get_output_postfix_pois(self):
        pois = super(HZZPOIMixin, self).get_output_postfix_pois()
        return tuple(p for p in pois if p in poi_data)


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
            "mv higgsCombineTest.MultiDimFit.mH{mass}.root {output}"
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
    scan_parameters = law.CSVParameter(
        default=(),
        description=(
            "scan definition; left empty here and fully set in modify_param_values "
            "for r_Njets_i"
        ),
        significant=False,
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
        reqs = super(HZZLikelihoodScan, self).workflow_requires()

        if self.use_snapshot:
            reqs["snapshot"] = HZZSnapshot.req_different_branching(self)

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
    # poi �оже п�и�оди� из AnyPOIsMixin (law.Parameter)

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
    # poi из AnyPOIsMixin

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
    pois = law.CSVParameter(
        default=("r_Njets_0",),
        description="POIs to overlay (only the first one is used here)",
    )

    @classmethod
    def modify_param_values(cls, params):
        params = super(HZZPlotMultipleLikelihoodScans, cls).modify_param_values(params)

        # Get the POI list, defaulting to r_Njets_0 if empty
        pois = params.get("pois", ("r_Njets_0",))
        if not pois:
            pois = ("r_Njets_0",)

        # DHI expects n_pois == 1 or 2; we only support 1 here
        poi = pois[0]
        params["pois"] = (poi,)

        # Keep the same scan definition as in HZZLikelihoodScan / HZZMergeLikelihoodScan
        params["scan_parameters"] = ((poi, 0.0, 2.0, 200),)

        return params

    def requires(self):
        # Effective POI used for the overlay (same logic as in modify_param_values)
        poi = (self.pois[0] if self.pois else "r_Njets_0")

        requirements = []
        for datacard_group in self.multi_datacards:
            merge_tasks = [
                HZZMergeLikelihoodScan(
                    version=self.version,
                    datacards=tuple(datacard_group),
                    workspace_name=self.workspace_name,
            #        hh_model=self.hh_model,
                    poi=poi,
                )
            ]
            requirements.append(merge_tasks)

        return requirements


# ---------------------------------------------------------------------------
# 7) HZZAllPOIs: orchestrate full chain for the 5 Njets POIs
# ---------------------------------------------------------------------------

class HZZAllPOIs(HZZBase):

    def requires(self):
        # Workspace and snapshot first
        ws = HZZCreateWorkspace(
            version=self.version,
            datacards=self.datacards,
            workspace_name=self.workspace_name,
    #        hh_model=self.hh_model,
        )
        snap = HZZSnapshot(
            version=self.version,
            datacards=self.datacards,
            workspace_name=self.workspace_name,
    #        hh_model=self.hh_model,
        )

        # The five POIs to scan
        pois = [f"r_Njets_{i}" for i in range(5)]

        # One likelihood scan per POI
        scans = [
            HZZLikelihoodScan(
                version=self.version,
                datacards=self.datacards,
                workspace_name=self.workspace_name,
        #        hh_model=self.hh_model,
                poi=p,
            )
            for p in pois
        ]

        # Merge outputs of each scan
        merges = [
            HZZMergeLikelihoodScan(
                version=self.version,
                datacards=self.datacards,
                workspace_name=self.workspace_name,
        #        hh_model=self.hh_model,
                poi=p,
            )
            for p in pois
        ]

        # Produce one plot per POI
        plots = [
            HZZPlotLikelihoodScan(
                version=self.version,
                datacards=self.datacards,
                workspace_name=self.workspace_name,
        #        hh_model=self.hh_model,
                poi=p,
            )
            for p in pois
        ]

        multi = HZZPlotMultipleLikelihoodScans(
            version=self.version,
            datacards=self.datacards,
            workspace_name=self.workspace_name,
        #    hh_model=self.hh_model,
            multi_datacards=(tuple(self.datacards),),
        )

        return {
            "workspace": ws,
            "snapshot": snap,
            "scans": scans,
            "merges": merges,
            "plots": plots,
            "multi": multi,
        }

    def output(self):
        return law.LocalFileTarget("hzz_all_pois.done")

    def run(self):
        self.output().dump("ok")
