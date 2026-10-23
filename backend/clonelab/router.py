"""FastAPI adapter for the independently callable CloneLab engine."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .diagnostics import optimize_digests
from .demos import list_demonstrations, run_demonstration
from .formats import parse_sequences
from .calibration import list_calibrations
from .gel import simulate_gel
from .hypotheses import construct_hypotheses
from .interpretation import interpret_bands
from .reports import export_report
from .reference import ReferenceNotReadyError, ReferenceRegistry
from .promoter import retrieve_promoter
from .restriction import UnknownEnzymeError, digest_sequence, restriction_map
from .schemas import (
    ConstructHypothesesRequest,
    DiagnosticWorkflowRequest,
    DiagnosticOptimizeRequest,
    DigestRequest,
    ProjectCreateRequest,
    PromoterRetrieveRequest,
    GelSimulationRequest,
    ReportExportRequest,
    ReferenceRetrieveRequest,
    ResultInterpretRequest,
    RestrictionMapRequest,
    SequenceImportRequest,
)
from .storage import CloneLabStore
from .workflow import optimize_construct_design

router = APIRouter(prefix="/api/v1/clonelab", tags=["CloneLab"])


def _store() -> CloneLabStore:
    default = Path(__file__).resolve().parents[1] / "data" / "clonelab.sqlite3"
    return CloneLabStore(os.environ.get("CLONELAB_DB", str(default)))


def _max_input_bases() -> int:
    return int(os.environ.get("CLONELAB_MAX_INPUT_BASES", "1000000"))


def _reference_registry() -> ReferenceRegistry:
    default = Path(__file__).resolve().parents[1] / "data" / "clonelab_references.json"
    return ReferenceRegistry(os.environ.get("CLONELAB_REFERENCE_MANIFEST", str(default)))


def _atlas_database() -> Path:
    default = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
    return Path(os.environ.get("GRN_DB_PATH", str(default)))


def _plasmid_fixture() -> Path:
    default = Path(__file__).resolve().parents[1] / "data/clonelab/pUC19_L09137.2.gb"
    return Path(os.environ.get("CLONELAB_PUC19", str(default)))


@router.get("/demonstrations")
def demonstrations():
    return {"demonstrations": list_demonstrations()}


@router.get("/demonstrations/{demonstration_id}")
def demonstration(demonstration_id: str):
    try:
        return run_demonstration(
            demonstration_id, registry=_reference_registry(),
            database_path=_atlas_database(), plasmid_path=_plasmid_fixture(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail="CloneLab release references are not installed") from exc
    except ReferenceNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects")
def create_project(request: ProjectCreateRequest):
    return _store().create_project(request.name, request.description, request.darwin_context)


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    project = _store().get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="CloneLab project not found")
    return project


@router.post("/sequences/import")
def import_sequences(request: SequenceImportRequest):
    limit = _max_input_bases()
    if len(request.content) > limit * 2:
        raise HTTPException(status_code=413, detail=f"sequence input exceeds configured limit of {limit} bases")
    try:
        records = parse_sequences(
            request.content,
            file_format=request.file_format,
            default_topology=request.default_topology,
            source=request.source,
        )
        if sum(len(record["sequence"]) for record in records) > limit:
            raise HTTPException(status_code=413, detail=f"sequence input exceeds configured limit of {limit} bases")
        stored = [_store().save_sequence(record, request.project_id) for record in records]
        return {"count": len(stored), "sequences": stored}
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/sequences/parse")
def parse_sequence_records(request: SequenceImportRequest):
    limit = _max_input_bases()
    try:
        records = parse_sequences(
            request.content,
            file_format=request.file_format,
            default_topology=request.default_topology,
            source=request.source,
        )
        if sum(len(record["sequence"]) for record in records) > limit:
            raise HTTPException(status_code=413, detail=f"sequence input exceeds configured limit of {limit} bases")
        return {"count": len(records), "sequences": records}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/sequences/{sequence_id}")
def get_sequence(sequence_id: str, include_bases: bool = True):
    sequence = _store().get_sequence(sequence_id, include_bases=include_bases)
    if sequence is None:
        raise HTTPException(status_code=404, detail="CloneLab sequence not found")
    return sequence


@router.post("/sequences/retrieve")
def retrieve_reference_sequence(request: ReferenceRetrieveRequest):
    try:
        return _reference_registry().retrieve(**request.model_dump())
    except ReferenceNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/sequences/promoter")
def retrieve_promoter_sequence(request: PromoterRetrieveRequest):
    try:
        return retrieve_promoter(
            _reference_registry(), _atlas_database(), **request.model_dump()
        )
    except ReferenceNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/gels/calibrations")
def gel_calibrations():
    return {"calibrations": list_calibrations()}


@router.post("/constructs/hypotheses")
def generate_construct_hypotheses(request: ConstructHypothesesRequest):
    try:
        hypotheses = construct_hypotheses(
            request.vector.sequence,
            request.insert.sequence,
            insertion_start=request.insertion_start,
            insertion_end=request.insertion_end,
            vector_topology=request.vector.topology,
            include_tandem=request.include_tandem,
        )
        return {"count": len(hypotheses), "hypotheses": hypotheses}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/gels/simulate")
def simulate_gel_endpoint(request: GelSimulationRequest):
    try:
        return simulate_gel(
            [lane.model_dump() for lane in request.lanes],
            ladder=request.ladder,
            min_visible_bp=request.min_visible_bp,
            max_visible_bp=request.max_visible_bp,
            resolution_fraction=request.resolution_fraction,
            calibration_id=request.calibration_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/results/interpret")
def interpret_results(request: ResultInterpretRequest):
    try:
        return interpret_bands(
            request.observed_bands_bp,
            request.predictions,
            tolerance_fraction=request.tolerance_fraction,
            tolerance_bp=request.tolerance_bp,
            max_missing=request.max_missing,
            max_unexpected=request.max_unexpected,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/reports/export")
def export_report_endpoint(request: ReportExportRequest):
    try:
        return export_report(request.project, request.analysis, output_format=request.output_format)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/workflows/diagnostic-digest")
def diagnostic_digest_workflow(request: DiagnosticWorkflowRequest):
    try:
        return optimize_construct_design(
            request.vector.sequence,
            request.insert.sequence,
            insertion_start=request.insertion_start,
            insertion_end=request.insertion_end,
            candidate_enzymes=request.candidate_enzymes,
            include_tandem=request.include_tandem,
            min_fragment_bp=request.min_fragment_bp,
            max_fragment_bp=request.max_fragment_bp,
        )
    except (ValueError, UnknownEnzymeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/restriction/map")
def map_restriction_sites(request: RestrictionMapRequest):
    try:
        return restriction_map(
            request.molecule.sequence,
            request.enzymes,
            topology=request.molecule.topology,
        )
    except (ValueError, UnknownEnzymeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/digests")
def digest(request: DigestRequest):
    try:
        return digest_sequence(
            request.molecule.sequence,
            request.enzymes,
            topology=request.molecule.topology,
            include_fragment_sequences=request.include_fragment_sequences,
        )
    except (ValueError, UnknownEnzymeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/assays/optimize")
def optimize_assays(request: DiagnosticOptimizeRequest):
    try:
        return optimize_digests(
            [hypothesis.model_dump() for hypothesis in request.hypotheses],
            request.candidate_enzymes,
            max_enzymes_per_digest=request.max_enzymes_per_digest,
            min_fragment_bp=request.min_fragment_bp,
            max_fragment_bp=request.max_fragment_bp,
            min_separation_bp=request.min_separation_bp,
            relative_resolution=request.relative_resolution,
            top=request.top,
        )
    except (ValueError, UnknownEnzymeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
