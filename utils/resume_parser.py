"""
Parse the resume PDF once, extract the skills you actually have, and derive
search keywords from them. The result is cached to data/resume_profile.json and
rebuilt automatically whenever the PDF changes.

This is what makes scoring/searching personal to *you* instead of a fixed table.
"""
import json
import re
from pathlib import Path

from pypdf import PdfReader

from config.config import DATA_DIR, RESUMES
from utils.logger import get_logger

logger = get_logger("resume_parser")
_CACHE = Path(DATA_DIR) / "resume_profile.json"

# Skills we know how to recognise. Multi-word entries are matched as phrases.
# Lowercase; add your own here any time.
SKILL_VOCAB = [
    # Languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "sql", "r",
    # Web / backend
    "react", "node.js", "node", "express", "angular", "vue", "next.js",
    "django", "flask", "fastapi", "spring", "mongodb", "mysql", "postgresql",
    "rest api", "graphql", "html", "css", "tailwind",
    # AI / ML / DL
    "pytorch", "tensorflow", "keras", "scikit-learn", "opencv", "cnn",
    "machine learning", "deep learning", "computer vision", "nlp",
    "transfer learning", "neural network",
    # LLM / agentic
    "langchain", "langgraph", "chromadb", "rag", "openai", "llm",
    "prompt engineering", "vector database", "pipecat", "deepgram",
    # Data analytics
    "numpy", "pandas", "matplotlib", "seaborn", "power bi", "tableau",
    "excel", "data analysis", "data analytics", "etl",
    # Cloud / tools
    "git", "docker", "kubernetes", "aws", "azure", "gcp", "linux",
]

# Detected skill -> job-search role term(s). Drives what we look for online.
_SKILL_TO_ROLE = {
    "python": ["Python Developer"],
    "java": ["Java Developer"],
    "react": ["React Developer", "Frontend Developer"],
    "node": ["Node.js Developer"],
    "node.js": ["Node.js Developer"],
    "django": ["Django Developer"],
    "flask": ["Flask Developer"],
    "machine learning": ["Machine Learning Engineer", "AI Engineer"],
    "deep learning": ["Deep Learning Engineer", "AI Engineer"],
    "pytorch": ["AI Engineer", "Machine Learning Engineer"],
    "tensorflow": ["AI Engineer", "Machine Learning Engineer"],
    "computer vision": ["Computer Vision Engineer"],
    "nlp": ["NLP Engineer"],
    "langchain": ["AI Engineer", "LLM Engineer"],
    "rag": ["AI Engineer", "LLM Engineer"],
    "llm": ["LLM Engineer", "Generative AI Engineer"],
    "pandas": ["Data Analyst"],
    "power bi": ["Data Analyst", "Business Analyst"],
    "tableau": ["Data Analyst"],
    "data analytics": ["Data Analyst"],
}

# Always-useful fresher framings appended to whatever roles we detect.
_FRESHER_VARIANTS = ["Junior {role}", "Graduate {role} Trainee"]


def _normalise(text: str) -> str:
    # Collapse the odd spacing pypdf produces (e.g. "W eb", "Node .js").
    return re.sub(r"\s+", " ", (text or "").lower())


def extract_text(pdf_path: str) -> str:
    try:
        reader = PdfReader(pdf_path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:
        logger.error("Could not read resume PDF '%s': %s", pdf_path, exc)
        return ""


def detect_skills(text: str) -> list[str]:
    norm = _normalise(text)
    found = []
    for skill in SKILL_VOCAB:
        # Word-ish boundary so 'r' / 'go' don't match inside other words.
        pattern = rf"(?<![a-z0-9.+#]){re.escape(skill)}(?![a-z0-9])"
        if re.search(pattern, norm):
            found.append(skill)
    return found


def derive_search_keywords(skills: list[str], limit: int = 12) -> list[str]:
    roles, seen = [], set()

    def add(term: str):
        if term.lower() not in seen:
            seen.add(term.lower())
            roles.append(term)

    for skill in skills:
        for role in _SKILL_TO_ROLE.get(skill, []):
            add(role)
    # Add a couple of fresher framings for the top roles.
    for role in list(roles)[:3]:
        for tmpl in _FRESHER_VARIANTS:
            add(tmpl.format(role=role))
    if not roles:  # nothing recognised -> safe generic fallback
        roles = ["Software Engineer", "Junior Software Engineer"]
    return roles[:limit]


def build_profile(pdf_path: str) -> dict:
    text = extract_text(pdf_path)
    skills = detect_skills(text)
    profile = {
        "resume_path": pdf_path,
        "mtime": Path(pdf_path).stat().st_mtime if Path(pdf_path).exists() else 0,
        "skills": skills,
        "search_keywords": derive_search_keywords(skills),
    }
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    logger.info("Built resume profile: %d skills -> %d search keywords",
                len(skills), len(profile["search_keywords"]))
    logger.info("Detected skills: %s", ", ".join(skills) or "(none)")
    return profile


def get_profile() -> dict:
    """Return the cached profile, rebuilding if the PDF changed or no cache."""
    pdf_path = RESUMES.get("default", "")
    pdf = Path(pdf_path)
    if not pdf.exists():
        logger.warning("Resume PDF not found at '%s'; using empty profile.", pdf_path)
        return {"skills": [], "search_keywords": []}

    if _CACHE.exists():
        try:
            cached = json.loads(_CACHE.read_text(encoding="utf-8"))
            if cached.get("mtime") == pdf.stat().st_mtime:
                return cached
        except (json.JSONDecodeError, OSError):
            pass
    return build_profile(str(pdf))
