"""Pydantic v2 schemas for incident report extraction."""

from pydantic import BaseModel, Field


class IncidentReport(BaseModel):
    """Structured representation of a fire/emergency incident report."""

    location: str = Field(
        ...,
        description="The street address or geographic location where the incident occurred.",
    )
    datetime: str = Field(
        ...,
        description="The date and time when the incident was reported or occurred (ISO-8601 preferred).",
    )
    incident_type: str = Field(
        ...,
        description="The category of the incident, e.g. 'structure fire', 'vehicle accident', 'hazmat spill'.",
    )
    units_involved: list[str] = Field(
        default_factory=list,
        description="List of responding units such as engine companies, ladder trucks, or ambulances.",
    )
    injuries: int = Field(
        default=0,
        description="Total number of reported injuries (civilian and firefighter combined).",
    )
    hazards: list[str] = Field(
        default_factory=list,
        description="Known hazards present at the scene, e.g. 'propane tanks', 'downed power lines'.",
    )
    summary: str = Field(
        ...,
        description="A concise one- or two-sentence summary of the incident.",
    )
