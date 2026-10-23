"""Pydantic contracts for the first CloneLab diagnostic-optimization slice."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .sequence import canonical_sequence, normalize_topology


class SequenceInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sequence: str = Field(min_length=1, max_length=1_000_000)
    topology: Literal["linear", "circular"] = "circular"
    accession: str | None = Field(default=None, max_length=200)
    source: str | None = Field(default=None, max_length=500)

    @field_validator("sequence")
    @classmethod
    def validate_sequence(cls, value: str) -> str:
        return canonical_sequence(value)

    @field_validator("topology")
    @classmethod
    def validate_topology(cls, value: str) -> str:
        return normalize_topology(value)


class HypothesisInput(SequenceInput):
    hypothesis_id: str = Field(min_length=1, max_length=100)
    label: str | None = Field(default=None, max_length=200)
    prior: float | None = Field(default=None, gt=0.0, le=1.0)


class RestrictionMapRequest(BaseModel):
    molecule: SequenceInput
    enzymes: list[str] = Field(min_length=1, max_length=50)


class DigestRequest(RestrictionMapRequest):
    include_fragment_sequences: bool = True


class DiagnosticOptimizeRequest(BaseModel):
    hypotheses: list[HypothesisInput] = Field(min_length=2, max_length=20)
    candidate_enzymes: list[str] = Field(min_length=1, max_length=40)
    max_enzymes_per_digest: int = Field(default=2, ge=1, le=2)
    min_fragment_bp: int = Field(default=50, ge=0)
    max_fragment_bp: int = Field(default=20_000, ge=1)
    min_separation_bp: int = Field(default=25, ge=0)
    relative_resolution: float = Field(default=0.05, ge=0.0, le=0.5)
    top: int = Field(default=10, ge=1, le=100)

    @field_validator("hypotheses")
    @classmethod
    def unique_hypotheses(cls, values: list[HypothesisInput]) -> list[HypothesisInput]:
        ids = [value.hypothesis_id for value in values]
        if len(ids) != len(set(ids)):
            raise ValueError("hypothesis_id values must be unique")
        supplied_priors = [v.prior for v in values if v.prior is not None]
        if supplied_priors and len(supplied_priors) != len(values):
            raise ValueError("either provide priors for every hypothesis or omit all priors")
        return values

    @field_validator("candidate_enzymes")
    @classmethod
    def unique_enzymes(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if not cleaned:
            raise ValueError("at least one candidate enzyme is required")
        return list(dict.fromkeys(cleaned))


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    darwin_context: dict = Field(default_factory=dict)


class SequenceImportRequest(BaseModel):
    content: str = Field(min_length=1)
    file_format: Literal["auto", "fasta", "genbank"] = "auto"
    default_topology: Literal["linear", "circular"] = "linear"
    source: str | None = Field(default=None, max_length=500)
    project_id: str | None = Field(default=None, max_length=100)


class ConstructHypothesesRequest(BaseModel):
    vector: SequenceInput
    insert: SequenceInput
    insertion_start: int = Field(ge=0)
    insertion_end: int | None = Field(default=None, ge=0)
    include_tandem: bool = False


class GelLaneInput(BaseModel):
    lane_id: str = Field(min_length=1, max_length=100)
    label: str | None = Field(default=None, max_length=200)
    fragment_lengths: list[int] = Field(default_factory=list, max_length=100)
    uncut_circular: bool = False


class GelSimulationRequest(BaseModel):
    lanes: list[GelLaneInput] = Field(min_length=1, max_length=30)
    ladder: str | None = "neb_1kb_plus_n0550"
    calibration_id: str | None = "neb_n0550_1pct_tbe_image_v1"
    min_visible_bp: int = Field(default=50, ge=1)
    max_visible_bp: int = Field(default=20_000, ge=1)
    resolution_fraction: float = Field(default=0.02, gt=0, le=0.25)


class ResultInterpretRequest(BaseModel):
    observed_bands_bp: list[int] = Field(min_length=1, max_length=100)
    predictions: dict[str, list[int]] = Field(min_length=1)
    tolerance_fraction: float = Field(default=0.08, ge=0, le=0.5)
    tolerance_bp: int = Field(default=25, ge=0)
    max_missing: int = Field(default=0, ge=0, le=20)
    max_unexpected: int = Field(default=0, ge=0, le=20)


class ReportExportRequest(BaseModel):
    project: dict
    analysis: dict
    output_format: Literal["json", "markdown"] = "json"


class DiagnosticWorkflowRequest(BaseModel):
    vector: SequenceInput
    insert: SequenceInput
    insertion_start: int = Field(ge=0)
    insertion_end: int | None = Field(default=None, ge=0)
    candidate_enzymes: list[str] = Field(min_length=1, max_length=40)
    include_tandem: bool = True
    min_fragment_bp: int = Field(default=50, ge=1)
    max_fragment_bp: int = Field(default=20_000, ge=1)


class ReferenceRetrieveRequest(BaseModel):
    species: str = Field(min_length=1, max_length=100)
    assembly: str = Field(min_length=1, max_length=100)
    record_id: str = Field(min_length=1, max_length=200)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    strand: Literal[-1, 1] = 1
    molecule_type: Literal["transcript", "genome"] | None = None


class PromoterRetrieveRequest(BaseModel):
    species: str = Field(min_length=1, max_length=100)
    gene_id: str = Field(min_length=1, max_length=200)
    upstream: int = Field(default=2000, ge=0, le=20_000)
    downstream: int = Field(default=500, ge=0, le=5_000)
