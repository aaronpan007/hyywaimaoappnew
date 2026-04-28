from app.schemas.common import CamelModel


class CaseStudy(CamelModel):
    project: str
    description: str


class CompanyProfileResponse(CamelModel):
    id: int
    company_name: str
    industry: str = ""
    website: str = ""
    established: str = ""
    employees: str = ""
    certifications: str = ""
    cooperation_models: str = ""
    products: list[str] = []
    competencies: list[str] = []
    case_studies: list[CaseStudy] = []
    collected_at: str = ""
    is_current: bool = False
