"""Central configuration loaded from .env"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# --- API Keys ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")  # "groq" or "gemini"
DATACOMMONS_API_KEY = os.getenv("DATACOMMONS_API_KEY", "")
DATACOMMONS_NL_API_KEY = os.getenv("DATACOMMONS_NL_API_KEY", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
EVENTREGISTRY_API_KEY = os.getenv("EVENTREGISTRY_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

# --- Memgraph ---
MEMGRAPH_HOST = os.getenv("MEMGRAPH_HOST", "127.0.0.1")
MEMGRAPH_PORT = int(os.getenv("MEMGRAPH_PORT", "7687"))
MEMGRAPH_USERNAME = os.getenv("MEMGRAPH_USERNAME", "")
MEMGRAPH_PASSWORD = os.getenv("MEMGRAPH_PASSWORD", "")

# --- Pipeline ---
RSS_SOURCE_FILE = PROJECT_ROOT / os.getenv("RSS_SOURCE_FILE", "data/rss_sources.csv")
NEWS_FETCH_LIMIT = int(os.getenv("NEWS_FETCH_LIMIT", "20"))
ARTICLE_TIMEOUT = int(os.getenv("ARTICLE_TIMEOUT", "15"))
EXTRACTION_MODEL = os.getenv("EXTRACTION_MODEL", "gemini-1.5-pro")

# --- Embeddings ---
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-004")
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.88"))

# --- System Flags ---
ENABLE_FEEDBACK_LOOP = os.getenv("ENABLE_FEEDBACK_LOOP", "true").lower() == "true"
ENABLE_SELF_CORRECTION = os.getenv("ENABLE_SELF_CORRECTION", "true").lower() == "true"
ENABLE_RSS_DISCOVERY = os.getenv("ENABLE_RSS_DISCOVERY", "false").lower() == "true"

# --- Paths ---
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
FAILED_DIR = DATA_DIR / "failed_extractions"
SAMPLE_NEWS_DIR = DATA_DIR / "sample_news"
CORRECTIONS_LOG = DATA_DIR / "corrections.log"

# Ensure directories exist
for d in [DATA_DIR, LOGS_DIR, FAILED_DIR, SAMPLE_NEWS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# --- Ontology ---
ALLOWED_NODE_LABELS = [
    "Country", "Location", "Resource", "Event",
    "Indicator", "Organization", "Company", "Policy",
    "Person", "Technology", "Vessel", "EconomicIndicator",
    "MilitaryAsset", "Agreement", "Infrastructure",
]

ALLOWED_RELATIONSHIP_TYPES = [
    "IMPORTS", "EXPORTS", "TRANSPORT_ROUTE_FOR", "CONFLICT_WITH",
    "THREATENS", "DISRUPTS", "AFFECTS", "CAUSES", "INFLUENCES",
    "CRITICAL_FOR", "IMPACTS",
    # Expanded relationship types for richer ontology
    "MEMBER_OF", "ALLIES_WITH", "SANCTIONS", "INVESTS_IN",
    "TRADES_WITH", "SUPPLIES", "DEVELOPS", "OPERATES_IN",
    "MANUFACTURES", "PARTNERS_WITH", "HOSTS", "PARTICIPATES_IN",
    "BORDERS", "PRODUCES", "CONTROLS", "FUNDS", "REGULATES",
    "COMPETES_WITH", "COOPERATES_WITH", "DEPENDS_ON",
    "HEADQUARTERED_IN", "SUBSIDIARY_OF", "EXPORTS_TO",
    "IMPORTS_FROM", "PROVIDES_SERVICES_TO", "FRONT_COMPANY_FOR",
    "MANAGES", "OPERATES", "ATTACKS", "SUSPENDS_OPERATIONS_IN",
    "SOURCE_OF", "TRANSFERRED_TO", "FACILITATES_TRADE_OF",
    "INCREASES", "DEFENSE_PARTNERSHIP_WITH", "SIGNS",
    "LEADS", "RESEARCHES", "DEPLOYS", "TRAINS",
    "MEDIATES", "EXPLOITS", "EMITS", "MITIGATES",
    "CONNECTS", "TRANSITS_THROUGH", "EXPORTS_OIL_VIA",
    "EXPORTS_LPG_VIA", "ATTACKED_IN", "WAIVES_SANCTIONS_TEMPORARILY_FOR",
]

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
SAVE_FAILED_EXTRACTIONS = os.getenv("SAVE_FAILED_EXTRACTIONS", "true").lower() == "true"
SAVE_RAW_ARTICLES = os.getenv("SAVE_RAW_ARTICLES", "true").lower() == "true"
