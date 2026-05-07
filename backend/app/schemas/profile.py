from typing import Any

from pydantic import Field

from app.schemas.common import CamelModel


class CompanyProfileResponse(CamelModel):
    id: int
    company_name: str
    one_line_intro: str = ""
    full_intro: str = ""
    location: str = ""
    industry: str = ""
    website: str = ""
    established: str = ""
    scale: str = ""
    employees: str = ""
    certifications: list[Any] | str = Field(default_factory=list)
    cooperation_models: list[Any] | str = Field(default_factory=list)
    products: list[Any] = Field(default_factory=list)
    competencies: list[Any] = Field(default_factory=list)
    target_customer_types: list[Any] = Field(default_factory=list)
    case_studies: list[Any] = Field(default_factory=list)
    unique_selling_points: list[Any] = Field(default_factory=list)
    customer_matching_guide: list[Any] = Field(default_factory=list)
    boundaries: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    profile_data: dict[str, Any] = Field(default_factory=dict)
    profile_markdown: str = ""
    collected_at: str = ""
    is_current: bool = False
