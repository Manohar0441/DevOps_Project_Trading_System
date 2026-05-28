import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd
import yfinance as yf


# =============================================================================
# CONFIG
# =============================================================================

SECTOR_KEY_MAP = {
    "Technology": "technology",
    "Healthcare": "healthcare",
    "Financial Services": "financial-services",
    "Energy": "energy",
    "Consumer Cyclical": "consumer-cyclical",
    "Consumer Defensive": "consumer-defensive",
    "Industrials": "industrials",
    "Utilities": "utilities",
    "Real Estate": "real-estate",
    "Basic Materials": "basic-materials",
    "Communication Services": "communication-services",
    "Services": "services",
}

SOURCE_WEIGHTS = {
    "industry_top": 8.0,
    "sector_top": 4.0,
    "etf_holding": 1.0,
}

DISALLOWED_EXCHANGE_MARKERS = {
    "OTC",
    "OTCM",
    "OTCQB",
    "OTCQX",
    "PNK",
    "GREY",
}

DISALLOWED_SYMBOL_SUFFIXES = (
    "-P",
    "-WS",
    "-WT",
    "-RT",
    ".WS",
    ".WT",
    ".RT",
)

TEXT_STOPWORDS = {
    "about",
    "after",
    "also",
    "among",
    "and",
    "business",
    "company",
    "companies",
    "develops",
    "for",
    "from",
    "global",
    "holdings",
    "inc",
    "including",
    "its",
    "offers",
    "operations",
    "plc",
    "products",
    "provides",
    "services",
    "solutions",
    "systems",
    "that",
    "the",
    "through",
    "using",
    "with",
    "worldwide",
}

MINIMUM_PEER_SCORE = 46.0
PRIMARY_SCORE_RATIO = 0.68
RELAXED_SCORE_RATIO = 0.55
RELAXED_MINIMUM_PEER_SCORE = 40.0
MAX_SIZE_RATIO = 40.0
MAX_WORKERS = 8

BUSINESS_MODEL_RULES: Dict[str, Tuple[str, ...]] = {
    "SaaS": ("software as a service", "subscription software", "enterprise software", "cloud software"),
    "Marketplace": ("marketplace", "buyers and sellers", "third party sellers", "merchant marketplace"),
    "Platform": ("platform", "ecosystem", "network platform", "digital platform"),
    "Bank": ("bank", "banking", "deposits", "commercial lending", "consumer lending"),
    "Insurance": ("insurance", "insurer", "underwriting", "premiums", "claims"),
    "Asset_Manager": ("asset management", "investment management", "fund management", "assets under management"),
    "Manufacturer": ("manufactures", "manufacturing", "produces", "assembly", "production facilities"),
    "Semiconductor": ("semiconductor", "integrated circuit", "chip", "chips"),
    "Semiconductor_Fabless": ("fabless", "chip design", "semiconductor design", "system on chip"),
    "Semiconductor_Foundry": ("foundry", "wafer fabrication", "semiconductor manufacturing", "process node"),
    "Semiconductor_Equipment": ("semiconductor equipment", "etch equipment", "deposition equipment", "wafer equipment"),
    "Consumer_Brand": ("brand portfolio", "consumer brands", "branded products", "brand management"),
    "Retail": ("retail stores", "retailer", "store network", "merchandise stores"),
    "Logistics": ("logistics", "freight", "shipping", "supply chain", "warehousing", "parcel"),
    "Telecom": ("telecommunications", "wireless", "broadband", "mobile network", "telecom services"),
    "Healthcare_Provider": ("hospital", "hospitals", "clinic", "healthcare services", "patient care", "care delivery"),
    "Pharma": ("pharmaceutical", "drug", "therapeutics", "medicines", "commercial therapeutics"),
    "Payments": ("payment processing", "payments", "merchant acquiring", "payment gateway", "digital payments"),
    "Exchange": ("exchange operator", "stock exchange", "trading venue", "futures exchange", "clearing house"),
    "Automotive": ("automotive", "vehicle manufacturer", "auto parts", "vehicles"),
    "Aerospace": ("aerospace", "aviation", "aircraft systems", "aircraft components"),
    "Media": ("media", "broadcast", "publishing", "content", "advertising-supported"),
    "Gaming": ("video games", "gaming", "interactive entertainment", "game publisher"),
    "Data_Provider": ("market data", "information services", "data provider", "ratings and analytics"),
    "Cybersecurity": ("cybersecurity", "endpoint security", "identity security", "network security", "security software"),
    "Cloud_Infrastructure": ("cloud infrastructure", "cloud computing", "compute services", "storage services", "infrastructure services"),
    "Fintech": ("fintech", "embedded finance", "digital finance", "financial technology"),
    "Biotech": ("biotechnology", "drug discovery", "clinical-stage", "biologic", "genetic medicine"),
    "E_Commerce": ("e-commerce", "online retail", "digital commerce", "online marketplace"),
    "Social_Network": ("social network", "social media", "social platform", "creator platform"),
    "Streaming": ("streaming", "video streaming", "music streaming", "streaming platform"),
    "Real_Estate": ("real estate", "property development", "property management", "property portfolio"),
    "REIT": ("reit", "real estate investment trust", "rental properties", "leased properties"),
    "Mining": ("mining", "minerals", "ore", "extraction", "commodity production"),
    "Utilities": ("utility", "regulated utility", "electric utility", "gas utility", "water utility"),
    "Defense_Contractor": ("defense contractor", "defense systems", "military systems", "government programs"),
    "Travel": ("travel", "airline", "cruise", "tourism", "transportation services"),
    "Hospitality": ("hotels", "resorts", "hospitality", "lodging"),
    "Food_Beverage": ("food and beverage", "packaged foods", "beverages", "restaurants"),
    "Chemicals": ("chemicals", "chemical products", "process chemistry"),
    "Industrial_Equipment": ("industrial equipment", "industrial machinery", "equipment services", "machinery"),
    "Construction_Materials": ("construction materials", "building products", "aggregates", "cement"),
    "Engineering_Services": ("engineering services", "engineering and construction", "project management"),
    "IT_Services": ("it services", "technology consulting", "digital transformation", "systems integration"),
    "Managed_Services": ("managed services", "outsourcing", "managed cloud", "managed network"),
    "Advertising": ("advertising agency", "advertising services", "marketing services"),
    "AdTech": ("advertising technology", "programmatic advertising", "ad platform", "demand-side platform"),
    "MarTech": ("marketing technology", "marketing automation", "customer engagement software"),
    "Hardware": ("hardware", "servers", "storage systems", "network equipment"),
    "AI_Platform": ("artificial intelligence", "machine learning platform", "generative ai", "ai software"),
    "DevTools": ("developer tools", "devops", "application monitoring", "software development tools"),
    "Renewable_Energy": ("renewable energy", "solar", "wind", "clean energy", "renewable power"),
    "Oil_Gas_Upstream": ("upstream", "exploration and production", "oil production", "gas production"),
    "Oil_Gas_Midstream": ("midstream", "pipelines", "terminal storage", "gathering and processing"),
    "Oil_Gas_Downstream": ("downstream", "refining", "fuel distribution", "petroleum products"),
    "Investment_Banking": ("investment banking", "capital markets", "advisory services", "mergers and acquisitions"),
    "Wealth_Management": ("wealth management", "private banking", "financial advisors", "advisory platform"),
    "Credit_Services": ("credit cards", "consumer lending", "point-of-sale financing", "credit services"),
    "Digital_Banking": ("digital bank", "mobile banking", "online bank", "neobank"),
    "Insurtech": ("insurtech", "digital insurance", "insurance platform"),
    "Healthtech": ("digital health", "healthcare software", "telehealth", "care management software"),
    "MedTech": ("medical device", "medical devices", "surgical device", "patient monitoring"),
    "Diagnostics": ("diagnostic", "diagnostics", "lab testing", "clinical assays"),
    "CRO": ("contract research", "clinical trials", "research organization", "drug development services"),
    "CDMO": ("contract development and manufacturing", "cdmo", "drug manufacturing services"),
    "EV_Manufacturer": ("electric vehicle", "electric vehicles", "battery electric", "ev manufacturer"),
    "EV_Charging": ("ev charging", "charging network", "charging stations"),
    "Autonomous_Driving": ("autonomous driving", "self-driving", "advanced driver assistance"),
    "Mobility_Platform": ("ride sharing", "mobility platform", "transport marketplace"),
    "Space_Tech": ("space technology", "launch services", "space systems"),
    "Satellite_Communications": ("satellite communications", "satellite services", "satellite network"),
    "GovTech": ("government software", "public sector software", "government technology"),
    "EdTech": ("education technology", "learning platform", "online education"),
    "Travel_Platform": ("travel platform", "travel marketplace", "travel search"),
    "Online_Travel_Agency": ("online travel", "travel booking", "travel reservations"),
    "Food_Delivery": ("food delivery", "restaurant marketplace", "delivery platform"),
    "Quick_Service_Restaurant": ("quick service restaurant", "fast food", "restaurant franchising"),
    "Casual_Dining": ("casual dining", "full service restaurant"),
    "Fine_Dining": ("fine dining", "upscale restaurant"),
    "Beverage_Alcoholic": ("beer", "spirits", "wine", "alcoholic beverages"),
    "Beverage_NonAlcoholic": ("soft drinks", "energy drinks", "non-alcoholic beverages"),
    "AgTech": ("precision agriculture", "agricultural technology", "farm software"),
    "Fertilizers": ("fertilizer", "potash", "nitrogen", "phosphate"),
    "Specialty_Chemicals": ("specialty chemicals", "performance chemicals", "advanced materials"),
    "Commodity_Chemicals": ("commodity chemicals", "basic chemicals", "petrochemicals"),
    "Industrial_Automation": ("industrial automation", "factory automation", "motion control"),
    "Digital_Marketing": ("digital marketing", "performance marketing", "search marketing"),
    "Content_Platform": ("content platform", "digital publishing", "content monetization"),
    "Creator_Economy": ("creator economy", "creator monetization", "fan subscriptions"),
    "Luxury_Goods": ("luxury goods", "luxury fashion", "high-end accessories"),
    "Apparel": ("apparel", "clothing", "garments"),
    "Footwear": ("footwear", "shoes", "athletic footwear"),
    "Home_Goods": ("home goods", "home furnishings", "home improvement"),
    "Consumer_Electronics": ("consumer electronics", "smartphones", "wearables", "connected devices"),
    "IoT_Platform": ("internet of things", "iot platform", "connected devices"),
    "Data_Analytics": ("data analytics", "analytics software", "business intelligence"),
    "Data_Warehousing": ("data warehouse", "data warehousing", "data lakehouse"),
    "Data_Integration": ("data integration", "etl", "data pipelines"),
    "API_Platform": ("api platform", "api management", "api gateway"),
    "Low_Code_No_Code": ("low-code", "no-code", "visual development"),
    "Open_Source_Commercial": ("open core", "open source software", "open-source platform"),
}

REVENUE_DRIVER_RULES: Dict[str, Tuple[str, ...]] = {
    "Subscriptions": ("subscription", "subscriptions", "recurring revenue", "subscription-based"),
    "Transaction_Fees": ("transaction fee", "transaction fees", "booking fees", "service charges"),
    "Ad_Revenue": ("advertising revenue", "advertising", "advertisers", "ad sales"),
    "Interest_Income": ("interest income", "net interest income", "loan portfolio"),
    "Asset_Fees": ("asset-based fee", "asset fees", "assets under management"),
    "Product_Sales": ("product sales", "product revenue", "product portfolio"),
    "Licensing": ("licensing", "license fees", "licensed"),
    "Commodity_Pricing": ("commodity prices", "oil prices", "gas prices", "metal prices", "spot prices"),
    "Usage_Fees": ("usage-based", "volume-based pricing", "pay as you go"),
    "Hardware_Sales": ("hardware sales", "device sales", "equipment sales"),
    "Services_Revenue": ("services revenue", "service revenue", "professional services"),
    "Data_Monetization": ("data licensing", "market data", "information services"),
    "API_Fees": ("api fees", "api usage", "api calls"),
    "Brokerage_Commissions": ("brokerage commissions", "trading commissions", "brokerage fees"),
    "Underwriting_Fees": ("underwriting fees", "origination fees", "underwriting"),
    "Management_Fees": ("management fees", "advisory fees", "fee-based assets"),
    "Performance_Fees": ("performance fees", "incentive fees", "carried interest"),
    "Royalties": ("royalties", "royalty income"),
    "Franchise_Fees": ("franchise fees", "franchise royalty"),
    "Maintenance_Fees": ("maintenance fees", "service contracts"),
    "Support_Fees": ("support fees", "technical support"),
    "Installation_Fees": ("installation fees", "implementation fees"),
    "Consulting_Fees": ("consulting fees", "consulting revenue", "advisory services"),
    "Advertising_Commissions": ("advertising commissions", "media buying"),
    "Marketplace_Take_Rate": ("take rate", "marketplace fees", "merchant fees"),
    "Payment_Processing_Fees": ("payment processing fees", "merchant processing"),
    "Interchange_Fees": ("interchange", "card fees"),
    "Spread_Income": ("spread income", "net interest margin", "spreads"),
    "Rental_Income": ("rental income", "rent revenue"),
    "Leasing_Fees": ("leasing fees", "lease revenue"),
    "Ticket_Sales": ("ticket sales", "attendance revenue"),
    "Sponsorship_Revenue": ("sponsorship", "sponsorship revenue"),
    "Content_Subscriptions": ("content subscriptions", "streaming subscriptions"),
    "In_App_Purchases": ("in-app purchases", "digital items"),
    "Microtransactions": ("microtransactions", "virtual goods"),
    "Cloud_Compute_Fees": ("compute fees", "cloud compute", "compute instances"),
    "Storage_Fees": ("storage fees", "cloud storage", "storage services"),
    "Network_Fees": ("network fees", "bandwidth fees", "connectivity services"),
    "Capacity_Charges": ("capacity charges", "contracted capacity"),
    "Toll_Revenue": ("toll revenue", "usage tolls"),
    "Subscription_Add_Ons": ("add-on subscriptions", "premium tier", "seat expansion"),
    "Warranty_Services": ("warranty", "extended warranty"),
    "Aftermarket_Parts_Sales": ("aftermarket parts", "replacement parts"),
}

REVENUE_DRIVER_PHRASES: Dict[str, str] = {
    "Subscriptions": "subscription revenue",
    "Transaction_Fees": "transaction fees",
    "Ad_Revenue": "digital advertising",
    "Interest_Income": "interest income",
    "Asset_Fees": "asset-based fees",
    "Product_Sales": "product sales",
    "Licensing": "software licensing",
    "Commodity_Pricing": "commodity pricing",
    "Usage_Fees": "usage-based pricing",
    "Hardware_Sales": "hardware sales",
    "Services_Revenue": "services revenue",
    "Data_Monetization": "data licensing",
    "API_Fees": "api usage fees",
    "Brokerage_Commissions": "brokerage commissions",
    "Underwriting_Fees": "underwriting fees",
    "Management_Fees": "management fees",
    "Performance_Fees": "performance fees",
    "Royalties": "royalty income",
    "Franchise_Fees": "franchise fees",
    "Maintenance_Fees": "maintenance contracts",
    "Support_Fees": "support contracts",
    "Installation_Fees": "implementation fees",
    "Consulting_Fees": "consulting fees",
    "Advertising_Commissions": "advertising commissions",
    "Marketplace_Take_Rate": "marketplace take rate",
    "Payment_Processing_Fees": "payment processing fees",
    "Interchange_Fees": "interchange fees",
    "Spread_Income": "spread income",
    "Rental_Income": "rental income",
    "Leasing_Fees": "leasing fees",
    "Ticket_Sales": "ticket sales",
    "Sponsorship_Revenue": "sponsorship revenue",
    "Content_Subscriptions": "content subscriptions",
    "In_App_Purchases": "in-app purchases",
    "Microtransactions": "microtransactions",
    "Cloud_Compute_Fees": "cloud compute fees",
    "Storage_Fees": "cloud storage fees",
    "Network_Fees": "network services",
    "Capacity_Charges": "capacity charges",
    "Toll_Revenue": "toll revenue",
    "Subscription_Add_Ons": "subscription add-ons",
    "Warranty_Services": "warranty services",
    "Aftermarket_Parts_Sales": "aftermarket parts",
}

DIRECT_PHRASE_RULES: Dict[str, Tuple[str, ...]] = {
    "enterprise software": ("enterprise software", "business software", "workflow software"),
    "subscription software": ("subscription software", "software subscriptions"),
    "cloud infrastructure": ("cloud infrastructure", "cloud computing", "infrastructure services"),
    "compute services": ("compute services", "compute instances"),
    "storage services": ("storage services", "cloud storage"),
    "payment processing": ("payment processing", "merchant processing"),
    "merchant acquiring": ("merchant acquiring", "merchant services"),
    "digital banking": ("digital banking", "mobile banking", "online bank"),
    "consumer lending": ("consumer lending", "credit cards", "point-of-sale financing"),
    "commercial lending": ("commercial lending", "business lending"),
    "insurance underwriting": ("insurance underwriting", "policy underwriting"),
    "asset management": ("asset management", "investment management"),
    "exchange operations": ("exchange operator", "trading venue"),
    "market data": ("market data", "pricing data", "reference data"),
    "cybersecurity software": ("cybersecurity", "security software"),
    "endpoint security": ("endpoint security", "endpoint protection"),
    "identity security": ("identity security", "identity management"),
    "data analytics": ("data analytics", "business intelligence"),
    "data warehousing": ("data warehouse", "data warehousing", "lakehouse"),
    "data integration": ("data integration", "data pipelines", "etl"),
    "api management": ("api management", "api gateway"),
    "developer tools": ("developer tools", "devops", "application monitoring"),
    "semiconductor design": ("chip design", "semiconductor design"),
    "wafer fabrication": ("wafer fabrication", "semiconductor manufacturing"),
    "semiconductor equipment": ("semiconductor equipment", "wafer equipment"),
    "industrial automation": ("industrial automation", "factory automation"),
    "industrial machinery": ("industrial machinery", "equipment systems"),
    "freight logistics": ("freight", "logistics", "supply chain"),
    "e-commerce retail": ("e-commerce", "online retail"),
    "store network": ("retail stores", "store network"),
    "consumer electronics": ("consumer electronics", "smartphones", "wearables"),
    "digital advertising": ("advertising revenue", "digital advertising"),
    "social networking": ("social network", "social media"),
    "streaming media": ("video streaming", "music streaming", "streaming platform"),
    "video games": ("video games", "gaming", "interactive entertainment"),
    "drug development": ("drug development", "therapeutics", "clinical-stage"),
    "clinical diagnostics": ("diagnostic", "clinical assays", "lab testing"),
    "medical devices": ("medical device", "patient monitoring"),
    "contract research": ("contract research", "clinical trials"),
    "drug manufacturing": ("contract development and manufacturing", "drug manufacturing"),
    "renewable power": ("renewable energy", "solar", "wind"),
    "oil production": ("oil production", "exploration and production"),
    "pipeline transport": ("pipelines", "midstream"),
    "petroleum refining": ("refining", "downstream"),
    "regulated utilities": ("regulated utility", "electric utility"),
    "mineral extraction": ("mining", "ore", "minerals"),
    "specialty chemicals": ("specialty chemicals", "performance chemicals"),
    "commodity chemicals": ("commodity chemicals", "petrochemicals"),
    "property leasing": ("leasing", "leased properties", "rental properties"),
    "travel booking": ("travel booking", "travel reservations"),
    "hotel operations": ("hotels", "lodging", "resorts"),
    "food delivery": ("food delivery", "delivery platform"),
    "restaurant franchising": ("restaurant franchising", "franchise fees"),
    "defense systems": ("defense systems", "military systems"),
    "aerospace systems": ("aerospace", "aircraft systems"),
}

SECTOR_MODEL_FALLBACKS: Dict[str, Tuple[str, ...]] = {
    "Technology": ("SaaS", "Cloud_Infrastructure", "Hardware"),
    "Healthcare": ("Pharma", "Biotech", "MedTech"),
    "Financial Services": ("Bank", "Payments", "Asset_Manager"),
    "Energy": ("Oil_Gas_Upstream", "Oil_Gas_Midstream", "Oil_Gas_Downstream"),
    "Consumer Cyclical": ("Retail", "E_Commerce", "Automotive"),
    "Consumer Defensive": ("Consumer_Brand", "Food_Beverage", "Retail"),
    "Industrials": ("Manufacturer", "Industrial_Equipment", "Logistics"),
    "Utilities": ("Utilities", "Renewable_Energy"),
    "Real Estate": ("REIT", "Real_Estate"),
    "Basic Materials": ("Mining", "Specialty_Chemicals", "Construction_Materials"),
    "Communication Services": ("Telecom", "Media", "Streaming"),
    "Services": ("IT_Services", "Managed_Services", "Travel"),
}

CYCLICAL_MODELS = {
    "Automotive",
    "Construction_Materials",
    "Commodity_Chemicals",
    "Energy_Producer",
    "Industrial_Equipment",
    "Manufacturer",
    "Mining",
    "Oil_Gas_Upstream",
    "Oil_Gas_Midstream",
    "Oil_Gas_Downstream",
    "Semiconductor",
    "Semiconductor_Fabless",
    "Semiconductor_Foundry",
    "Semiconductor_Equipment",
    "Specialty_Chemicals",
}


# =============================================================================
# SMALL HELPERS
# =============================================================================

def _clean_symbol(value: Any) -> Optional[str]:
    if value is None:
        return None

    s = str(value).strip().upper()
    if not s or s in {"NAN", "NONE", "NULL"}:
        return None

    if len(s) > 15 or any(ch.isspace() for ch in s):
        return None

    return s


def _unique_preserve_order(items: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []

    for item in items:
        item = _clean_symbol(item)
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)

    return out


def _first_non_empty(*values: Any) -> Optional[str]:
    for value in values:
        if value is None:
            continue

        text = str(value).strip()
        if text:
            return text

    return None


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(numeric):
        return None

    return numeric


def _normalize_sector_key(sector: Optional[str]) -> Optional[str]:
    if not sector:
        return None

    sector = sector.strip()
    return SECTOR_KEY_MAP.get(sector, sector.lower().replace(" ", "-"))


def _extract_symbols(obj: Any) -> List[str]:
    """
    Extract ticker symbols from DataFrames, Series, dicts, lists, tuples, or scalars.
    Works defensively because yfinance responses can vary by endpoint/version.
    """
    symbols: List[str] = []

    if obj is None:
        return symbols

    if isinstance(obj, pd.DataFrame):
        candidate_cols = [
            "symbol",
            "Symbol",
            "ticker",
            "Ticker",
            "companySymbol",
            "company_symbol",
            "holdingSymbol",
            "holding_symbol",
        ]
        for col in candidate_cols:
            if col in obj.columns:
                symbols.extend(obj[col].tolist())

        if not symbols and obj.index is not None:
            symbols.extend([str(x) for x in obj.index.tolist()])

        return [_clean_symbol(x) for x in symbols if _clean_symbol(x)]

    if isinstance(obj, pd.Series):
        symbols.extend([str(x) for x in obj.tolist()])
        return [_clean_symbol(x) for x in symbols if _clean_symbol(x)]

    if isinstance(obj, dict):
        for key in ("symbol", "Symbol", "ticker", "Ticker", "holdings", "data"):
            if key in obj:
                symbols.extend(_extract_symbols(obj[key]))

        if not symbols:
            symbols.extend(list(obj.keys()))

        return [_clean_symbol(x) for x in symbols if _clean_symbol(x)]

    if isinstance(obj, (list, tuple, set)):
        for item in obj:
            if isinstance(item, dict):
                symbols.extend(_extract_symbols(item))
            else:
                symbols.append(str(item))

        return [_clean_symbol(x) for x in symbols if _clean_symbol(x)]

    return [_clean_symbol(obj)] if _clean_symbol(obj) else []


def _tokenize_text(*values: Any) -> Set[str]:
    tokens: Set[str] = set()

    for value in values:
        if not value:
            continue

        for token in re.findall(r"[A-Za-z][A-Za-z0-9&-]{2,}", str(value).lower()):
            token = token.strip("-")
            if not token or token in TEXT_STOPWORDS:
                continue
            tokens.add(token)

    return tokens


def _first_finite_float(*values: Any) -> Optional[float]:
    for value in values:
        numeric = _as_float(value)
        if numeric is not None:
            return numeric
    return None


def _normalize_match_text(*values: Any) -> str:
    text = " ".join(str(value) for value in values if value is not None).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return f" {text} " if text else " "


def _clean_phrase(value: Any) -> str:
    text = str(value or "").lower().replace("&", " and ").replace("_", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _dedupe_phrases(values: Iterable[str], limit: Optional[int] = None) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    generic_phrases = {
        "technology",
        "healthcare",
        "industrials",
        "services",
        "communication services",
        "basic materials",
        "financial services",
        "consumer cyclical",
        "consumer defensive",
    }

    for value in values:
        phrase = _clean_phrase(value)
        if not phrase or phrase in seen or phrase in generic_phrases:
            continue
        seen.add(phrase)
        out.append(phrase)
        if limit is not None and len(out) >= limit:
            break

    return out


def _pattern_match_count(text: str, patterns: Iterable[str]) -> int:
    return sum(1 for pattern in patterns if _clean_phrase(pattern) and f" {_clean_phrase(pattern)} " in text)


def _normalized_phrase_set(values: Iterable[str]) -> Set[str]:
    return {phrase for phrase in (_clean_phrase(value) for value in values) if phrase}


def _phrase_similarity(left: Iterable[str], right: Iterable[str]) -> float:
    return _jaccard_similarity(_normalized_phrase_set(left), _normalized_phrase_set(right))


def _negative_overlap(left_negative: Iterable[str], right_positive: Iterable[str]) -> float:
    negatives = _normalized_phrase_set(left_negative)
    positives = _normalized_phrase_set(right_positive)
    if not negatives or not positives:
        return 0.0
    overlap = negatives & positives
    return len(overlap) / max(1, min(len(negatives), len(positives)))


def _classification_phrases(industry: Optional[str], sector: Optional[str], industry_key: Optional[str]) -> List[str]:
    phrases = []

    if industry:
        phrases.append(industry)
    if industry_key:
        phrases.append(str(industry_key).replace("-", " "))

    sector_tag_map = {
        "Communication Services": "communications infrastructure",
        "Energy": "energy infrastructure",
        "Financial Services": "financial services",
        "Healthcare": "healthcare services",
        "Real Estate": "real estate",
        "Technology": "technology infrastructure",
        "Utilities": "regulated utilities",
    }
    if sector in sector_tag_map:
        phrases.append(sector_tag_map[sector])

    return _dedupe_phrases(phrases, limit=3)


def _keyword_templates_for_model(model: str) -> Tuple[List[str], List[str], List[str]]:
    software_models = {
        "AI_Platform",
        "API_Platform",
        "Cloud_Infrastructure",
        "Cybersecurity",
        "Data_Analytics",
        "Data_Integration",
        "Data_Warehousing",
        "DevTools",
        "EdTech",
        "GovTech",
        "Healthtech",
        "IoT_Platform",
        "Low_Code_No_Code",
        "Managed_Services",
        "MarTech",
        "Open_Source_Commercial",
        "SaaS",
    }
    financial_models = {
        "Asset_Manager",
        "Bank",
        "Credit_Services",
        "Digital_Banking",
        "Exchange",
        "Fintech",
        "Insurance",
        "Insurtech",
        "Investment_Banking",
        "Payments",
        "Wealth_Management",
    }
    semiconductor_models = {
        "Semiconductor",
        "Semiconductor_Equipment",
        "Semiconductor_Fabless",
        "Semiconductor_Foundry",
    }
    healthcare_models = {
        "Biotech",
        "CDMO",
        "CRO",
        "Diagnostics",
        "Healthcare_Provider",
        "MedTech",
        "Pharma",
    }
    industrial_models = {
        "Aerospace",
        "Automotive",
        "Defense_Contractor",
        "Engineering_Services",
        "Industrial_Automation",
        "Industrial_Equipment",
        "Logistics",
        "Manufacturer",
    }
    energy_models = {
        "Chemicals",
        "Commodity_Chemicals",
        "Construction_Materials",
        "Energy_Producer",
        "Fertilizers",
        "Mining",
        "Oil_Gas_Downstream",
        "Oil_Gas_Midstream",
        "Oil_Gas_Upstream",
        "Renewable_Energy",
        "Specialty_Chemicals",
        "Utilities",
    }
    media_models = {
        "AdTech",
        "Advertising",
        "Content_Platform",
        "Creator_Economy",
        "Gaming",
        "Media",
        "Social_Network",
        "Streaming",
    }
    travel_models = {
        "Food_Delivery",
        "Hospitality",
        "Online_Travel_Agency",
        "Quick_Service_Restaurant",
        "Travel",
        "Travel_Platform",
    }
    real_estate_models = {"REIT", "Real_Estate"}

    if model == "SaaS":
        return (
            ["enterprise software", "subscription software", "workflow automation"],
            ["software integrations", "annual recurring revenue", "seat expansion"],
            ["enterprise software", "application software", "subscription software"],
        )
    if model == "Cloud_Infrastructure":
        return (
            ["cloud infrastructure", "compute services", "storage services"],
            ["network services", "enterprise workloads", "usage-based pricing"],
            ["cloud infrastructure", "infrastructure software", "enterprise software"],
        )
    if model == "Cybersecurity":
        return (
            ["cybersecurity software", "endpoint security", "identity security"],
            ["threat detection", "security subscriptions", "enterprise accounts"],
            ["cybersecurity software", "enterprise software", "security infrastructure"],
        )
    if model == "AI_Platform":
        return (
            ["artificial intelligence", "machine learning platform", "model deployment"],
            ["ai workloads", "inference services", "developer platform"],
            ["artificial intelligence software", "enterprise software", "platform software"],
        )
    if model == "Data_Analytics":
        return (
            ["data analytics", "business intelligence", "decision support"],
            ["dashboards", "analytics subscriptions", "enterprise data"],
            ["data analytics", "enterprise software", "analytics software"],
        )
    if model == "Data_Warehousing":
        return (
            ["data warehousing", "cloud data warehouse", "data lakehouse"],
            ["query workloads", "storage services", "analytics infrastructure"],
            ["data warehousing", "data infrastructure", "enterprise software"],
        )
    if model == "Data_Integration":
        return (
            ["data integration", "data pipelines", "etl workflows"],
            ["workflow orchestration", "enterprise connectors", "usage-based pricing"],
            ["data integration", "enterprise software", "data infrastructure"],
        )
    if model == "API_Platform":
        return (
            ["api platform", "api management", "developer integrations"],
            ["api usage fees", "developer tools", "platform software"],
            ["api infrastructure", "developer tools", "enterprise software"],
        )
    if model == "DevTools":
        return (
            ["developer tools", "application monitoring", "devops automation"],
            ["usage-based pricing", "engineering workflows", "software integrations"],
            ["developer tools", "enterprise software", "software infrastructure"],
        )
    if model in {"Marketplace", "Platform"}:
        return (
            ["digital platform", "network effects", "transaction flows"],
            ["merchant onboarding", "buyer seller matching", "platform monetization"],
            ["platform software", "digital marketplaces", "transaction infrastructure"],
        )
    if model == "E_Commerce":
        return (
            ["e-commerce retail", "online merchandising", "fulfillment network"],
            ["marketplace take rate", "consumer demand", "digital storefront"],
            ["e-commerce", "online retail", "consumer internet"],
        )
    if model == "Payments":
        return (
            ["payment processing", "merchant acquiring", "digital payments"],
            ["transaction fees", "interchange economics", "payment acceptance"],
            ["payment processing", "payments infrastructure", "consumer fintech"],
        )
    if model in {"Bank", "Digital_Banking"}:
        return (
            ["deposit banking", "commercial lending", "consumer lending"],
            ["net interest income", "card issuance", "digital banking"],
            ["banking", "consumer finance", "deposit institutions"],
        )
    if model == "Credit_Services":
        return (
            ["consumer lending", "credit underwriting", "card issuance"],
            ["interest income", "point-of-sale financing", "credit risk"],
            ["consumer finance", "credit services", "lending"],
        )
    if model in {"Insurance", "Insurtech"}:
        return (
            ["insurance underwriting", "policy administration", "claims management"],
            ["risk pricing", "distribution partners", "renewal retention"],
            ["insurance carriers", "insurance distribution", "risk underwriting"],
        )
    if model in {"Asset_Manager", "Wealth_Management"}:
        return (
            ["asset management", "fee-based assets", "investment products"],
            ["client assets", "advisory platform", "wealth advisory"],
            ["asset management", "wealth management", "investment services"],
        )
    if model == "Investment_Banking":
        return (
            ["capital markets", "deal advisory", "underwriting fees"],
            ["mergers and acquisitions", "transaction advisory", "institutional clients"],
            ["investment banking", "capital markets", "financial advisory"],
        )
    if model == "Exchange":
        return (
            ["exchange operations", "trade clearing", "market data"],
            ["listing services", "transaction fees", "derivatives trading"],
            ["financial exchanges", "market infrastructure", "market data"],
        )
    if model == "Fintech":
        return (
            ["financial software", "digital finance", "embedded finance"],
            ["transaction fees", "software integrations", "consumer fintech"],
            ["fintech", "digital finance", "payments software"],
        )
    if model == "Semiconductor_Fabless":
        return (
            ["semiconductor design", "chip architecture", "fabless semiconductors"],
            ["intellectual property", "wafer outsourcing", "design wins"],
            ["semiconductor fabless", "semiconductors", "chip design"],
        )
    if model == "Semiconductor_Foundry":
        return (
            ["wafer fabrication", "process technology", "foundry services"],
            ["capacity utilization", "advanced packaging", "manufacturing scale"],
            ["semiconductor foundry", "semiconductors", "chip manufacturing"],
        )
    if model == "Semiconductor_Equipment":
        return (
            ["semiconductor equipment", "wafer tools", "process equipment"],
            ["installed base", "service contracts", "capital equipment"],
            ["semiconductor equipment", "chip manufacturing", "industrial equipment"],
        )
    if model == "Semiconductor":
        return (
            ["semiconductors", "integrated circuits", "chip design"],
            ["end-market exposure", "manufacturing partners", "product cycles"],
            ["semiconductors", "chip design", "electronic components"],
        )
    if model == "Healthcare_Provider":
        return (
            ["patient care", "care delivery", "provider network"],
            ["procedure volumes", "reimbursement rates", "care settings"],
            ["healthcare providers", "care delivery", "health services"],
        )
    if model == "Pharma":
        return (
            ["drug development", "commercial therapeutics", "branded medicines"],
            ["regulatory approvals", "patent portfolio", "sales force"],
            ["pharmaceuticals", "biopharma", "commercial therapeutics"],
        )
    if model == "Biotech":
        return (
            ["drug discovery", "clinical pipelines", "biologic therapeutics"],
            ["clinical milestones", "platform science", "partnered programs"],
            ["biotechnology", "drug development", "clinical-stage therapeutics"],
        )
    if model == "Diagnostics":
        return (
            ["clinical diagnostics", "diagnostic testing", "lab assays"],
            ["test volumes", "instrument placements", "reagent sales"],
            ["diagnostics", "lab testing", "clinical testing"],
        )
    if model == "MedTech":
        return (
            ["medical devices", "procedure volumes", "patient monitoring"],
            ["installed base", "clinical adoption", "service contracts"],
            ["medical devices", "health technology", "procedure-based care"],
        )
    if model == "CRO":
        return (
            ["contract research", "clinical trials", "regulatory support"],
            ["billable hours", "sponsor programs", "trial management"],
            ["contract research", "clinical services", "drug development services"],
        )
    if model == "CDMO":
        return (
            ["drug manufacturing", "development services", "fill finish"],
            ["capacity utilization", "customer programs", "regulatory compliance"],
            ["contract manufacturing pharma", "drug manufacturing", "pharma services"],
        )
    if model == "Industrial_Equipment":
        return (
            ["industrial machinery", "equipment services", "aftermarket parts"],
            ["installed base", "service contracts", "capital equipment"],
            ["industrial equipment", "machinery", "aftermarket services"],
        )
    if model == "Industrial_Automation":
        return (
            ["industrial automation", "factory controls", "motion control"],
            ["software integration", "installed base", "automation systems"],
            ["industrial automation", "factory automation", "industrial technology"],
        )
    if model == "Logistics":
        return (
            ["freight logistics", "transport networks", "warehouse operations"],
            ["shipment volumes", "routing efficiency", "contract logistics"],
            ["logistics", "transportation services", "supply chain"],
        )
    if model == "Manufacturer":
        return (
            ["industrial manufacturing", "assembly operations", "product engineering"],
            ["plant utilization", "aftermarket support", "distribution channels"],
            ["industrial manufacturing", "product manufacturing", "capital goods"],
        )
    if model == "Automotive":
        return (
            ["vehicle production", "auto platforms", "dealer network"],
            ["unit sales", "parts content", "consumer financing"],
            ["automotive", "vehicle manufacturing", "mobility"],
        )
    if model == "EV_Manufacturer":
        return (
            ["electric vehicles", "battery systems", "vehicle software"],
            ["production ramp", "charging ecosystem", "direct sales"],
            ["electric vehicles", "automotive", "mobility"],
        )
    if model == "Telecom":
        return (
            ["telecom services", "wireless subscribers", "broadband internet"],
            ["network coverage", "service bundles", "subscriber retention"],
            ["telecom services", "communications infrastructure", "wireless carriers"],
        )
    if model == "Social_Network":
        return (
            ["social networking", "user engagement", "digital advertising"],
            ["ad targeting", "creator tools", "consumer internet"],
            ["social media", "digital advertising", "consumer internet"],
        )
    if model == "Streaming":
        return (
            ["streaming media", "content subscriptions", "content library"],
            ["subscriber growth", "content spend", "audience retention"],
            ["streaming media", "consumer internet", "digital media"],
        )
    if model == "Gaming":
        return (
            ["video games", "live services", "in-app purchases"],
            ["player engagement", "content pipeline", "digital items"],
            ["interactive entertainment", "video games", "digital media"],
        )
    if model in media_models:
        return (
            ["digital advertising", "audience monetization", "content distribution"],
            ["sponsorship revenue", "platform reach", "campaign performance"],
            ["digital media", "advertising", "consumer internet"],
        )
    if model == "Retail":
        return (
            ["store network", "merchandise sales", "retail operations"],
            ["same-store sales", "inventory turns", "private label"],
            ["retail", "consumer discretionary", "store-based retail"],
        )
    if model == "Consumer_Brand":
        return (
            ["branded products", "category management", "consumer demand"],
            ["distribution channels", "pricing power", "repeat purchases"],
            ["consumer brands", "packaged goods", "brand-led retail"],
        )
    if model == "Consumer_Electronics":
        return (
            ["consumer electronics", "device sales", "connected devices"],
            ["product launches", "hardware sales", "service attach rates"],
            ["consumer electronics", "hardware", "connected devices"],
        )
    if model == "Food_Delivery":
        return (
            ["food delivery", "restaurant marketplace", "last-mile logistics"],
            ["take rates", "consumer orders", "courier density"],
            ["food delivery", "local commerce", "consumer internet"],
        )
    if model in {"Travel_Platform", "Online_Travel_Agency"}:
        return (
            ["travel booking", "online travel", "accommodation supply"],
            ["booking volumes", "transaction fees", "marketing efficiency"],
            ["online travel", "travel platforms", "consumer internet"],
        )
    if model == "Hospitality":
        return (
            ["hotel operations", "room revenue", "occupancy rates"],
            ["daily rates", "franchise mix", "lodging demand"],
            ["hospitality", "lodging", "travel services"],
        )
    if model == "Quick_Service_Restaurant":
        return (
            ["restaurant franchising", "same-store sales", "menu innovation"],
            ["franchise fees", "store growth", "consumer traffic"],
            ["quick service restaurants", "restaurants", "franchise models"],
        )
    if model == "Renewable_Energy":
        return (
            ["renewable power", "solar generation", "wind generation"],
            ["contracted capacity", "power purchase agreements", "asset yields"],
            ["renewable power", "utilities", "energy infrastructure"],
        )
    if model == "Oil_Gas_Upstream":
        return (
            ["oil production", "gas production", "reserve development"],
            ["commodity pricing", "drilling activity", "production volumes"],
            ["oil and gas upstream", "energy production", "commodity producers"],
        )
    if model == "Oil_Gas_Midstream":
        return (
            ["pipeline transport", "terminal storage", "capacity contracts"],
            ["throughput volumes", "take or pay", "regulated tariffs"],
            ["oil and gas midstream", "energy infrastructure", "pipeline operators"],
        )
    if model == "Oil_Gas_Downstream":
        return (
            ["petroleum refining", "fuel distribution", "product spreads"],
            ["refining margins", "throughput volumes", "distribution network"],
            ["oil and gas downstream", "petroleum refining", "fuel distribution"],
        )
    if model == "Utilities":
        return (
            ["regulated utilities", "power distribution", "grid infrastructure"],
            ["rate base", "customer meters", "allowed returns"],
            ["regulated utilities", "power infrastructure", "electric utilities"],
        )
    if model == "Mining":
        return (
            ["mineral extraction", "ore production", "commodity volumes"],
            ["realized prices", "reserve life", "processing costs"],
            ["mining", "commodity producers", "extractive industries"],
        )
    if model in {"Chemicals", "Commodity_Chemicals", "Specialty_Chemicals", "Fertilizers"}:
        tag = "specialty chemicals" if model == "Specialty_Chemicals" else "commodity chemicals"
        if model == "Fertilizers":
            tag = "fertilizers"
        return (
            [tag, "process chemistry", "industrial inputs"],
            ["volume production", "input costs", "distribution network"],
            [tag, "chemicals", "materials"],
        )
    if model in {"REIT", "Real_Estate"}:
        return (
            ["property leasing", "rental income", "occupied assets"],
            ["lease terms", "occupancy rates", "asset portfolio"],
            ["real estate", "property leasing", "income-producing assets"],
        )
    if model == "Aerospace":
        return (
            ["aerospace systems", "aircraft components", "aviation services"],
            ["backlog", "program execution", "aftermarket parts"],
            ["aerospace", "aviation systems", "industrial technology"],
        )
    if model == "Defense_Contractor":
        return (
            ["defense systems", "government contracts", "program awards"],
            ["budget exposure", "backlog", "mission systems"],
            ["defense", "government contractors", "aerospace and defense"],
        )
    if model in travel_models:
        return (
            ["travel demand", "consumer bookings", "service network"],
            ["ticket sales", "occupancy rates", "consumer traffic"],
            ["travel services", "consumer services", "leisure"],
        )
    if model in real_estate_models:
        return (
            ["property assets", "lease revenue", "real estate operations"],
            ["occupancy", "asset mix", "capital recycling"],
            ["real estate", "property leasing", "asset ownership"],
        )
    if model in industrial_models:
        return (
            ["industrial operations", "contracted backlog", "service revenue"],
            ["installed base", "project execution", "aftermarket support"],
            ["industrials", "capital goods", "engineering"],
        )
    if model in energy_models:
        return (
            ["energy infrastructure", "commodity exposure", "physical assets"],
            ["volume growth", "price realization", "asset utilization"],
            ["energy", "materials", "physical infrastructure"],
        )
    if model in financial_models:
        return (
            ["financial services", "fee revenue", "client balances"],
            ["distribution channels", "advisory relationships", "regulated products"],
            ["financial services", "regulated finance", "capital markets"],
        )
    if model in healthcare_models:
        return (
            ["healthcare products", "clinical adoption", "regulated markets"],
            ["reimbursement dynamics", "sales channels", "regulatory compliance"],
            ["healthcare", "regulated health markets", "clinical services"],
        )
    if model in semiconductor_models:
        return (
            ["chip design", "semiconductor demand", "manufacturing scale"],
            ["product cycles", "capital intensity", "end-market exposure"],
            ["semiconductors", "electronic components", "chip supply chain"],
        )
    if model in software_models:
        return (
            ["enterprise software", "recurring revenue", "platform workflows"],
            ["customer retention", "software integrations", "usage expansion"],
            ["enterprise software", "software infrastructure", "recurring software"],
        )

    base_phrase = _clean_phrase(model)
    return (
        [base_phrase, "operating model", "revenue streams"],
        ["market position", "distribution channels", "cost structure"],
        [base_phrase],
    )


def _default_revenue_drivers_for_model(model: str) -> List[str]:
    if model == "Cloud_Infrastructure":
        return ["Cloud_Compute_Fees", "Storage_Fees", "Network_Fees", "Usage_Fees"]
    if model in {"SaaS", "Cybersecurity", "AI_Platform", "API_Platform", "Data_Analytics", "Data_Integration", "Data_Warehousing", "DevTools", "GovTech", "EdTech", "Healthtech", "Low_Code_No_Code", "MarTech", "Open_Source_Commercial"}:
        return ["Subscriptions", "Subscription_Add_Ons", "Support_Fees", "Licensing"]
    if model in {"Marketplace", "Platform", "E_Commerce", "Travel_Platform", "Online_Travel_Agency", "Food_Delivery", "Mobility_Platform"}:
        return ["Transaction_Fees", "Marketplace_Take_Rate", "Advertising_Commissions", "Subscriptions"]
    if model in {"Payments", "Fintech"}:
        return ["Payment_Processing_Fees", "Transaction_Fees", "Interchange_Fees", "Subscriptions"]
    if model in {"Bank", "Digital_Banking", "Credit_Services"}:
        return ["Interest_Income", "Spread_Income", "Interchange_Fees", "Brokerage_Commissions"]
    if model in {"Insurance", "Insurtech"}:
        return ["Underwriting_Fees", "Interest_Income", "Services_Revenue"]
    if model in {"Asset_Manager", "Wealth_Management"}:
        return ["Management_Fees", "Asset_Fees", "Performance_Fees", "Consulting_Fees"]
    if model == "Investment_Banking":
        return ["Underwriting_Fees", "Consulting_Fees", "Brokerage_Commissions"]
    if model == "Exchange":
        return ["Transaction_Fees", "Data_Monetization", "Licensing", "Brokerage_Commissions"]
    if model in {"Media", "Social_Network", "AdTech", "Advertising", "Digital_Marketing", "Content_Platform", "Creator_Economy"}:
        return ["Ad_Revenue", "Advertising_Commissions", "Subscriptions", "Sponsorship_Revenue"]
    if model == "Streaming":
        return ["Content_Subscriptions", "Ad_Revenue", "Subscriptions"]
    if model == "Gaming":
        return ["Product_Sales", "In_App_Purchases", "Microtransactions", "Subscriptions"]
    if model in {"Telecom", "Utilities", "Oil_Gas_Midstream"}:
        return ["Usage_Fees", "Network_Fees", "Capacity_Charges", "Subscriptions"]
    if model in {"REIT", "Real_Estate"}:
        return ["Rental_Income", "Leasing_Fees", "Services_Revenue"]
    if model in {"Oil_Gas_Upstream", "Oil_Gas_Downstream", "Energy_Producer", "Mining", "Commodity_Chemicals", "Specialty_Chemicals", "Chemicals", "Fertilizers"}:
        return ["Commodity_Pricing", "Product_Sales", "Services_Revenue"]
    if model in {"Manufacturer", "Industrial_Equipment", "Industrial_Automation", "Automotive", "Aerospace", "Defense_Contractor", "Consumer_Electronics", "Hardware", "Semiconductor", "Semiconductor_Fabless", "Semiconductor_Foundry", "Semiconductor_Equipment", "MedTech", "Diagnostics"}:
        return ["Product_Sales", "Services_Revenue", "Aftermarket_Parts_Sales", "Maintenance_Fees"]
    if model in {"Healthcare_Provider", "CRO", "CDMO", "IT_Services", "Managed_Services", "Engineering_Services", "Logistics"}:
        return ["Services_Revenue", "Consulting_Fees", "Maintenance_Fees", "Installation_Fees"]
    if model in {"Retail", "Consumer_Brand", "Food_Beverage", "Quick_Service_Restaurant", "Casual_Dining", "Fine_Dining", "Beverage_Alcoholic", "Beverage_NonAlcoholic", "Apparel", "Footwear", "Luxury_Goods", "Home_Goods"}:
        return ["Product_Sales", "Licensing", "Franchise_Fees", "Subscriptions"]
    if model in {"Travel", "Hospitality"}:
        return ["Ticket_Sales", "Services_Revenue", "Sponsorship_Revenue", "Franchise_Fees"]
    return ["Product_Sales", "Services_Revenue", "Subscriptions"]


def _default_negative_keywords_for_model(model: str) -> List[str]:
    if model in {"SaaS", "Cloud_Infrastructure", "Cybersecurity", "AI_Platform", "Data_Analytics", "Data_Integration", "Data_Warehousing", "DevTools", "GovTech", "EdTech", "Healthtech", "API_Platform", "Low_Code_No_Code", "Open_Source_Commercial"}:
        return ["hardware sales", "retail stores", "commodity production", "bank lending", "insurance underwriting", "property ownership"]
    if model in {"Marketplace", "Platform", "E_Commerce", "Travel_Platform", "Online_Travel_Agency", "Food_Delivery", "Mobility_Platform"}:
        return ["inventory manufacturing", "bank lending", "insurance underwriting", "oil production", "drug development", "property ownership"]
    if model in {"Bank", "Digital_Banking", "Credit_Services"}:
        return ["payment processing", "insurance underwriting", "asset management", "semiconductor design", "retail stores", "commodity production"]
    if model in {"Insurance", "Insurtech"}:
        return ["bank lending", "asset management", "payment processing", "semiconductor design", "retail stores", "oil production"]
    if model in {"Asset_Manager", "Wealth_Management", "Investment_Banking", "Exchange", "Fintech"}:
        return ["bank lending", "insurance underwriting", "payment processing", "retail stores", "commodity production", "drug manufacturing"]
    if model in {"Manufacturer", "Industrial_Equipment", "Industrial_Automation", "Automotive", "Aerospace", "Defense_Contractor", "Semiconductor", "Semiconductor_Fabless", "Semiconductor_Foundry", "Semiconductor_Equipment", "Consumer_Electronics", "Hardware"}:
        return ["subscription software", "bank lending", "insurance underwriting", "asset management", "social networking", "property leasing"]
    if model in {"Oil_Gas_Upstream", "Oil_Gas_Midstream", "Oil_Gas_Downstream", "Energy_Producer", "Mining", "Utilities", "Renewable_Energy", "Chemicals", "Specialty_Chemicals", "Commodity_Chemicals", "Construction_Materials"}:
        return ["subscription software", "payment processing", "social networking", "digital advertising", "bank lending", "asset management"]
    if model in {"Retail", "Consumer_Brand", "Food_Beverage", "Quick_Service_Restaurant", "Casual_Dining", "Fine_Dining", "Beverage_Alcoholic", "Beverage_NonAlcoholic", "Luxury_Goods", "Apparel", "Footwear", "Home_Goods", "Travel", "Hospitality"}:
        return ["bank lending", "insurance underwriting", "semiconductor design", "oil production", "medical devices", "cloud infrastructure"]
    if model in {"Media", "AdTech", "Advertising", "Digital_Marketing", "Social_Network", "Streaming", "Gaming", "Content_Platform", "Creator_Economy"}:
        return ["bank lending", "insurance underwriting", "semiconductor fabrication", "oil production", "drug development", "property leasing"]
    if model in {"Healthcare_Provider", "Pharma", "Biotech", "Diagnostics", "MedTech", "CRO", "CDMO"}:
        return ["bank lending", "payment processing", "retail stores", "oil production", "social networking", "property leasing"]
    if model in {"REIT", "Real_Estate"}:
        return ["subscription software", "payment processing", "drug development", "semiconductor design", "insurance underwriting", "bank lending"]
    return ["bank lending", "insurance underwriting", "retail stores", "commodity production", "property ownership", "digital advertising"]


def _default_customer_type_for_model(model: str) -> str:
    b2c_models = {
        "Apparel",
        "Beverage_Alcoholic",
        "Beverage_NonAlcoholic",
        "Consumer_Brand",
        "Consumer_Electronics",
        "E_Commerce",
        "EV_Manufacturer",
        "Fine_Dining",
        "Food_Beverage",
        "Gaming",
        "Home_Goods",
        "Hospitality",
        "Luxury_Goods",
        "Quick_Service_Restaurant",
        "Retail",
        "Social_Network",
        "Streaming",
        "Travel",
    }
    hybrid_models = {
        "Bank",
        "Credit_Services",
        "Digital_Banking",
        "Exchange",
        "Fintech",
        "Food_Delivery",
        "Healthcare_Provider",
        "Insurance",
        "Insurtech",
        "Media",
        "Online_Travel_Agency",
        "Payments",
        "Telecom",
        "Travel_Platform",
        "Utilities",
    }

    if model in b2c_models:
        return "B2C"
    if model in hybrid_models:
        return "Hybrid"
    return "B2B"


def _default_capital_intensity_for_model(model: str) -> str:
    asset_light_models = {
        "AI_Platform",
        "API_Platform",
        "Asset_Manager",
        "Bank",
        "Content_Platform",
        "Creator_Economy",
        "Credit_Services",
        "Cybersecurity",
        "Data_Analytics",
        "Data_Integration",
        "Data_Provider",
        "Data_Warehousing",
        "DevTools",
        "Digital_Banking",
        "Digital_Marketing",
        "EdTech",
        "Exchange",
        "Fintech",
        "GovTech",
        "Insurtech",
        "IT_Services",
        "Managed_Services",
        "MarTech",
        "Marketplace",
        "Open_Source_Commercial",
        "Payments",
        "Platform",
        "SaaS",
        "Social_Network",
        "Streaming",
        "Wealth_Management",
    }
    asset_heavy_models = {
        "Aerospace",
        "Automotive",
        "CDMO",
        "Chemicals",
        "Commodity_Chemicals",
        "Construction_Materials",
        "Consumer_Electronics",
        "Defense_Contractor",
        "Energy_Producer",
        "EV_Charging",
        "EV_Manufacturer",
        "Fertilizers",
        "Healthcare_Provider",
        "Hospitality",
        "Industrial_Equipment",
        "Logistics",
        "Manufacturer",
        "Mining",
        "Oil_Gas_Downstream",
        "Oil_Gas_Midstream",
        "Oil_Gas_Upstream",
        "REIT",
        "Real_Estate",
        "Renewable_Energy",
        "Satellite_Communications",
        "Semiconductor_Equipment",
        "Semiconductor_Foundry",
        "Space_Tech",
        "Specialty_Chemicals",
        "Telecom",
        "Travel",
        "Utilities",
    }

    if model == "Cloud_Infrastructure":
        return "Asset_Heavy"
    if model in asset_light_models:
        return "Asset_Light"
    if model in asset_heavy_models:
        return "Asset_Heavy"
    return "Moderate"


def _collect_direct_phrases(text: str) -> Dict[str, float]:
    matches: Dict[str, float] = {}
    for phrase, patterns in DIRECT_PHRASE_RULES.items():
        score = _pattern_match_count(text, patterns)
        if score:
            matches[phrase] = float(score)
    return matches


def _select_business_models(
    text: str,
    industry: Optional[str],
    sector: Optional[str],
) -> List[str]:
    scores: Dict[str, float] = {}

    for label, patterns in BUSINESS_MODEL_RULES.items():
        score = float(_pattern_match_count(text, patterns))
        if score:
            scores[label] = score

    for label in SECTOR_MODEL_FALLBACKS.get(sector or "", ()):
        scores[label] = scores.get(label, 0.0) + 0.25

    if industry:
        industry_text = _clean_phrase(industry)
        if "semiconductor" in industry_text:
            scores["Semiconductor"] = scores.get("Semiconductor", 0.0) + 1.0
        if "software" in industry_text:
            scores["SaaS"] = scores.get("SaaS", 0.0) + 0.5
        if "bank" in industry_text:
            scores["Bank"] = scores.get("Bank", 0.0) + 1.0
        if "insurance" in industry_text:
            scores["Insurance"] = scores.get("Insurance", 0.0) + 1.0
        if "asset management" in industry_text:
            scores["Asset_Manager"] = scores.get("Asset_Manager", 0.0) + 1.0
        if "reit" in industry_text:
            scores["REIT"] = scores.get("REIT", 0.0) + 1.0

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    chosen: List[str] = []
    for label, score in ranked:
        if score <= 0:
            continue
        if label == "Semiconductor" and any(
            specific in chosen for specific in ("Semiconductor_Fabless", "Semiconductor_Foundry", "Semiconductor_Equipment")
        ):
            continue
        if label in {"Bank", "Insurance", "Asset_Manager"} and "Financial Services" == sector and len(chosen) >= 1:
            pass
        chosen.append(label)
        if len(chosen) >= 2:
            break

    if not chosen:
        chosen.extend(list(SECTOR_MODEL_FALLBACKS.get(sector or "", ("Manufacturer",)))[:2])

    return chosen[:2]


def _select_revenue_drivers(text: str, business_models: List[str]) -> List[str]:
    scores: Dict[str, float] = {}

    for driver, patterns in REVENUE_DRIVER_RULES.items():
        score = float(_pattern_match_count(text, patterns))
        if score:
            scores[driver] = score

    for model in business_models:
        for idx, driver in enumerate(_default_revenue_drivers_for_model(model)):
            scores[driver] = scores.get(driver, 0.0) + max(0.5, 2.5 - idx * 0.4)

    ranked = [driver for driver, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))]
    drivers = ranked[:5]

    if len(drivers) < 3:
        for fallback in ("Product_Sales", "Services_Revenue", "Subscriptions"):
            if fallback not in drivers:
                drivers.append(fallback)
            if len(drivers) >= 3:
                break

    return drivers[:5]


def _select_customer_type(text: str, business_models: List[str]) -> str:
    b2b_score = 0.0
    b2c_score = 0.0

    enterprise_markers = ("enterprise", "businesses", "institutions", "merchants", "providers", "government")
    consumer_markers = ("consumers", "households", "shoppers", "travelers", "players", "subscribers", "patients")

    b2b_score += float(_pattern_match_count(text, enterprise_markers))
    b2c_score += float(_pattern_match_count(text, consumer_markers))

    for model in business_models:
        customer_type = _default_customer_type_for_model(model)
        if customer_type == "B2B":
            b2b_score += 1.0
        elif customer_type == "B2C":
            b2c_score += 1.0
        else:
            b2b_score += 0.75
            b2c_score += 0.75

    if b2b_score >= 1.5 and b2c_score >= 1.5:
        return "Hybrid"
    if b2c_score > b2b_score:
        return "B2C"
    return "B2B"


def _select_capital_intensity(business_models: List[str], sector: Optional[str]) -> str:
    if any(_default_capital_intensity_for_model(model) == "Asset_Heavy" for model in business_models):
        return "Asset_Heavy"
    if any(_default_capital_intensity_for_model(model) == "Moderate" for model in business_models):
        return "Moderate"
    if sector in {"Energy", "Real Estate", "Utilities"}:
        return "Asset_Heavy"
    return "Asset_Light"


def _select_growth_profile(
    revenue_growth: Optional[float],
    operating_margin: Optional[float],
    business_models: List[str],
    sector: Optional[str],
) -> str:
    if revenue_growth is None:
        if any(model in CYCLICAL_MODELS for model in business_models):
            return "Cyclical"
        if sector in {"Utilities", "Real Estate", "Consumer Defensive"}:
            return "Mature"
        return "Moderate_Growth"

    if revenue_growth > 0.30:
        return "Hyper_Growth"
    if revenue_growth > 0.15:
        return "High_Growth"
    if revenue_growth > 0.05:
        return "Moderate_Growth"
    if revenue_growth > 0.03:
        return "Low_Growth"
    if revenue_growth >= 0.0:
        if operating_margin is not None and operating_margin >= 0.10:
            return "Mature"
        return "Low_Growth"
    return "Declining"


def _select_industry_tags(
    text: str,
    business_models: List[str],
    industry: Optional[str],
    sector: Optional[str],
    industry_key: Optional[str],
) -> List[str]:
    scores: Dict[str, float] = {}

    for phrase in _classification_phrases(industry, sector, industry_key):
        scores[phrase] = scores.get(phrase, 0.0) + 3.0

    direct_phrases = _collect_direct_phrases(text)
    for phrase, score in direct_phrases.items():
        scores[phrase] = scores.get(phrase, 0.0) + score

    for model in business_models:
        _, _, tags = _keyword_templates_for_model(model)
        for idx, tag in enumerate(tags):
            scores[tag] = scores.get(tag, 0.0) + max(1.0, 4.0 - idx * 0.5)

    ranked = [phrase for phrase, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))]
    tags = _dedupe_phrases(ranked, limit=6)

    if len(tags) < 3:
        for model in business_models:
            core, _, _ = _keyword_templates_for_model(model)
            for phrase in core:
                cleaned = _clean_phrase(phrase)
                if cleaned not in tags:
                    tags.append(cleaned)
                if len(tags) >= 3:
                    break
            if len(tags) >= 3:
                break

    return tags[:6]


def _select_keywords(
    text: str,
    business_models: List[str],
    revenue_drivers: List[str],
    industry_tags: List[str],
    industry: Optional[str],
    sector: Optional[str],
    industry_key: Optional[str],
) -> Tuple[List[str], List[str]]:
    core_scores: Dict[str, float] = {}
    secondary_scores: Dict[str, float] = {}

    for phrase, score in _collect_direct_phrases(text).items():
        core_scores[phrase] = core_scores.get(phrase, 0.0) + 5.0 + score

    for phrase in _classification_phrases(industry, sector, industry_key):
        core_scores[phrase] = core_scores.get(phrase, 0.0) + 3.0

    for phrase in industry_tags:
        core_scores[phrase] = core_scores.get(phrase, 0.0) + 3.5

    for model in business_models:
        core_phrases, secondary_phrases, _ = _keyword_templates_for_model(model)
        for idx, phrase in enumerate(core_phrases):
            core_scores[phrase] = core_scores.get(phrase, 0.0) + max(1.5, 4.0 - idx * 0.5)
        for idx, phrase in enumerate(secondary_phrases):
            secondary_scores[phrase] = secondary_scores.get(phrase, 0.0) + max(1.0, 3.0 - idx * 0.4)

    for driver in revenue_drivers:
        phrase = REVENUE_DRIVER_PHRASES.get(driver, _clean_phrase(driver))
        secondary_scores[phrase] = secondary_scores.get(phrase, 0.0) + 2.0

    ranked_core = [phrase for phrase, _ in sorted(core_scores.items(), key=lambda item: (-item[1], item[0]))]
    ranked_secondary = [phrase for phrase, _ in sorted(secondary_scores.items(), key=lambda item: (-item[1], item[0]))]

    core_keywords = _dedupe_phrases(ranked_core, limit=10)
    if len(core_keywords) < 8:
        for phrase in ranked_secondary:
            cleaned = _clean_phrase(phrase)
            if cleaned not in core_keywords:
                core_keywords.append(cleaned)
            if len(core_keywords) >= 8:
                break

    secondary_keywords: List[str] = []
    for phrase in ranked_secondary + ranked_core:
        cleaned = _clean_phrase(phrase)
        if cleaned and cleaned not in core_keywords and cleaned not in secondary_keywords:
            secondary_keywords.append(cleaned)
        if len(secondary_keywords) >= 8:
            break

    if len(secondary_keywords) < 6:
        for extra in (
            "market share",
            "distribution channels",
            "pricing power",
            "customer retention",
            "installed base",
            "volume growth",
        ):
            cleaned = _clean_phrase(extra)
            if cleaned not in core_keywords and cleaned not in secondary_keywords:
                secondary_keywords.append(cleaned)
            if len(secondary_keywords) >= 6:
                break

    return core_keywords[:12], secondary_keywords[:10]


def _select_negative_keywords(business_models: List[str], industry_tags: List[str]) -> List[str]:
    negatives: List[str] = []
    for model in business_models:
        negatives.extend(_default_negative_keywords_for_model(model))

    if any("cloud infrastructure" in tag or "enterprise software" in tag for tag in industry_tags):
        negatives.extend(["commodity production", "retail stores"])
    if any("banking" in tag or "consumer finance" in tag for tag in industry_tags):
        negatives.extend(["oil production", "semiconductor design"])
    if any("real estate" in tag for tag in industry_tags):
        negatives.extend(["payment processing", "drug development"])

    negatives.extend(["property ownership", "commodity production", "bank lending"])
    return _dedupe_phrases(negatives, limit=8)


def extract_structured_peer_features(
    company_name: str,
    ticker: str,
    business_summary: Optional[str],
    industry: Optional[str],
    sector: Optional[str],
    industry_key: Optional[str] = None,
    revenue_growth: Optional[float] = None,
    operating_margin: Optional[float] = None,
) -> Dict[str, Any]:
    text = _normalize_match_text(company_name, ticker, business_summary, industry, sector, industry_key)
    business_models = _select_business_models(text, industry, sector)
    revenue_drivers = _select_revenue_drivers(text, business_models)
    customer_type = _select_customer_type(text, business_models)
    capital_intensity = _select_capital_intensity(business_models, sector)
    growth_profile = _select_growth_profile(revenue_growth, operating_margin, business_models, sector)
    industry_tags = _select_industry_tags(text, business_models, industry, sector, industry_key)
    core_keywords, secondary_keywords = _select_keywords(
        text,
        business_models,
        revenue_drivers,
        industry_tags,
        industry,
        sector,
        industry_key,
    )
    negative_keywords = _select_negative_keywords(business_models, industry_tags)

    return {
        "business_model": business_models[:2],
        "revenue_drivers": revenue_drivers[:5],
        "customer_type": customer_type,
        "capital_intensity": capital_intensity,
        "growth_profile": growth_profile,
        "core_keywords": core_keywords[:12],
        "secondary_keywords": secondary_keywords[:10],
        "negative_keywords": negative_keywords[:10],
        "industry_tags": industry_tags[:6],
    }


def _profile_structured_features(profile: Dict[str, Any]) -> Dict[str, Any]:
    structured = profile.get("structured_features")
    return structured if isinstance(structured, dict) else {}


def _positive_feature_phrases(profile: Dict[str, Any]) -> List[str]:
    structured = _profile_structured_features(profile)
    phrases: List[str] = []
    phrases.extend(structured.get("industry_tags", []))
    phrases.extend(structured.get("core_keywords", []))
    phrases.extend(structured.get("secondary_keywords", []))

    for driver in structured.get("revenue_drivers", []):
        phrases.append(REVENUE_DRIVER_PHRASES.get(driver, _clean_phrase(driver)))

    for model in structured.get("business_model", []):
        core_phrases, _, tags = _keyword_templates_for_model(model)
        phrases.extend(core_phrases[:1])
        phrases.extend(tags[:1])

    return _dedupe_phrases(phrases)


def _jaccard_similarity(left: Set[str], right: Set[str]) -> float:
    if not left or not right:
        return 0.0

    union = left | right
    if not union:
        return 0.0

    return len(left & right) / len(union)


def _bounded_similarity(left: Optional[float], right: Optional[float], scale: float) -> float:
    if left is None or right is None or scale <= 0:
        return 0.0

    diff = abs(float(left) - float(right))
    return max(0.0, 1.0 - min(diff / scale, 1.0))


def _ratio_band(left: Optional[float], right: Optional[float]) -> Optional[float]:
    if left is None or right is None or left <= 0 or right <= 0:
        return None

    higher = max(float(left), float(right))
    lower = min(float(left), float(right))
    if lower <= 0:
        return None

    return higher / lower


def _log_similarity(left: Optional[float], right: Optional[float]) -> float:
    """
    Returns 1.0 when equal, approaching 0 as values diverge.
    Uses log scale for market cap and revenue similarity.
    """
    if left is None or right is None:
        return 0.0

    try:
        left = float(left)
        right = float(right)
        if left <= 0 or right <= 0:
            return 0.0

        diff = abs(math.log(left) - math.log(right))
        return max(0.0, 1.0 - min(diff / math.log(10), 1.0))
    except Exception:
        return 0.0


def _issuer_key(profile: Dict[str, Any]) -> str:
    name = _first_non_empty(profile.get("long_name"), profile.get("symbol")) or ""
    normalized = name.lower()
    normalized = re.sub(r"\bclass\s+[a-z0-9]+\b", " ", normalized)
    normalized = re.sub(r"\bseries\s+[a-z0-9]+\b", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    return normalized or str(profile.get("symbol") or "").upper()


def _contains_disallowed_exchange(exchange: Optional[str]) -> bool:
    if not exchange:
        return False

    exchange_text = str(exchange).upper()
    return any(marker in exchange_text for marker in DISALLOWED_EXCHANGE_MARKERS)


def _is_common_stock_symbol(symbol: Optional[str]) -> bool:
    symbol = _clean_symbol(symbol)
    if not symbol:
        return False

    if any(marker in symbol for marker in ("^", "/", "=")):
        return False

    return not any(symbol.endswith(suffix) for suffix in DISALLOWED_SYMBOL_SUFFIXES)


def _add_symbols_with_source(target: Dict[str, Set[str]], source: str, symbols: Iterable[str]) -> None:
    for symbol in _unique_preserve_order(symbols):
        target.setdefault(symbol, set()).add(source)


# =============================================================================
# YFINANCE LOOKUPS
# =============================================================================

@lru_cache(maxsize=2048)
def get_ticker_info(symbol: str) -> Dict[str, Any]:
    """
    Cached info fetch. yfinance info can be incomplete, so all access is defensive.
    """
    symbol = _clean_symbol(symbol)
    if not symbol:
        return {}

    try:
        return yf.Ticker(symbol).info or {}
    except Exception:
        return {}


def get_company_profile(symbol: str) -> Dict[str, Any]:
    info = get_ticker_info(symbol)

    sector = _first_non_empty(info.get("sector"), info.get("sectorName"))
    industry = _first_non_empty(
        info.get("industry"),
        info.get("industryName"),
        info.get("industryDisp"),
    )
    sector_key = _first_non_empty(info.get("sectorKey"), _normalize_sector_key(sector))
    industry_key = _first_non_empty(info.get("industryKey"))

    quote_type = _first_non_empty(info.get("quoteType"))
    market_cap = _as_float(info.get("marketCap"))
    revenue = _as_float(info.get("totalRevenue"))
    revenue_growth = _first_finite_float(
        info.get("revenueGrowth"),
        info.get("earningsGrowth"),
        info.get("earningsQuarterlyGrowth"),
    )
    gross_margin = _as_float(info.get("grossMargins"))
    operating_margin = _as_float(info.get("operatingMargins"))
    beta = _as_float(info.get("beta"))

    long_name = _first_non_empty(info.get("longName"), info.get("shortName"), symbol)
    summary = _first_non_empty(
        info.get("longBusinessSummary"),
        info.get("description"),
        info.get("businessSummary"),
    )

    country = _first_non_empty(info.get("country"))
    exchange = _first_non_empty(info.get("exchange"), info.get("fullExchangeName"))
    currency = _first_non_empty(info.get("financialCurrency"), info.get("currency"))

    structured_features = extract_structured_peer_features(
        company_name=long_name or symbol,
        ticker=symbol,
        business_summary=summary,
        industry=industry,
        sector=sector,
        industry_key=industry_key,
        revenue_growth=revenue_growth,
        operating_margin=operating_margin,
    )

    industry_tokens = _tokenize_text(
        industry,
        industry_key,
        *structured_features.get("industry_tags", []),
        *structured_features.get("business_model", []),
    )
    business_tokens = _tokenize_text(
        long_name,
        industry,
        summary,
        *structured_features.get("core_keywords", []),
        *structured_features.get("secondary_keywords", []),
        *structured_features.get("revenue_drivers", []),
    )

    return {
        "symbol": _clean_symbol(symbol),
        "sector": sector,
        "industry": industry,
        "sector_key": sector_key,
        "industry_key": industry_key,
        "quote_type": quote_type,
        "market_cap": market_cap,
        "revenue": revenue,
        "revenue_growth": revenue_growth,
        "gross_margin": gross_margin,
        "operating_margin": operating_margin,
        "beta": beta,
        "country": country,
        "exchange": exchange,
        "currency": currency,
        "long_name": long_name,
        "industry_tokens": industry_tokens,
        "business_tokens": business_tokens,
        "structured_features": structured_features,
        "info": info,
    }


def get_sector_obj(sector_key: Optional[str]):
    if not sector_key:
        return None

    try:
        return yf.Sector(sector_key)
    except Exception:
        return None


def get_industry_obj(industry_key: Optional[str]):
    if not industry_key:
        return None

    try:
        return yf.Industry(industry_key)
    except Exception:
        return None


# =============================================================================
# UNIVERSE BUILDERS
# =============================================================================

def get_universe_from_sector(company_profile: Dict[str, Any]) -> List[str]:
    """
    Secondary universe: sector leaders.
    """
    sector_obj = get_sector_obj(company_profile.get("sector_key"))
    if not sector_obj:
        return []

    candidates: List[str] = []
    try:
        candidates.extend(_extract_symbols(getattr(sector_obj, "top_companies", None)))
    except Exception:
        pass

    return _unique_preserve_order(candidates)


def get_universe_from_industry(company_profile: Dict[str, Any]) -> List[str]:
    """
    Primary universe: industry leaders and top performers.
    We only pull growth names when the industry universe is too thin.
    """
    industry_obj = get_industry_obj(company_profile.get("industry_key"))
    if not industry_obj:
        return []

    candidates: List[str] = []
    for attr in ("top_companies", "top_performing_companies"):
        try:
            candidates.extend(_extract_symbols(getattr(industry_obj, attr, None)))
        except Exception:
            continue

    deduped = _unique_preserve_order(candidates)
    if len(deduped) >= 6:
        return deduped

    try:
        candidates.extend(_extract_symbols(getattr(industry_obj, "top_growth_companies", None)))
    except Exception:
        pass

    return _unique_preserve_order(candidates)


def get_universe_from_etf_fallback(sector: Optional[str], limit_holdings: int = 10) -> List[str]:
    """
    Last-resort fallback: use sector ETF top holdings.
    """
    sector_key = _normalize_sector_key(sector)
    if not sector_key:
        return []

    sector_obj = get_sector_obj(sector_key)
    if not sector_obj:
        return []

    etf_candidates: List[str] = []
    try:
        etf_candidates.extend(_extract_symbols(getattr(sector_obj, "top_etfs", None)))
    except Exception:
        pass

    etf_candidates = _unique_preserve_order(etf_candidates)
    holdings: List[str] = []

    for etf in etf_candidates[:5]:
        try:
            funds_data = yf.Ticker(etf).funds_data
            top_holdings = getattr(funds_data, "top_holdings", None)
            holdings.extend(_extract_symbols(top_holdings))
            if len(holdings) >= limit_holdings * 3:
                break
        except Exception:
            continue

    return _unique_preserve_order(holdings)


def build_peer_universe(ticker: str) -> Tuple[Dict[str, Any], Dict[str, Set[str]]]:
    """
    Build a candidate universe with source labels so the scorer can trust
    industry-derived names more than loose ETF fallbacks.
    """
    profile = get_company_profile(ticker)

    sources: Dict[str, Set[str]] = {}
    _add_symbols_with_source(sources, "industry_top", get_universe_from_industry(profile))
    _add_symbols_with_source(sources, "sector_top", get_universe_from_sector(profile))

    if len(sources) < 12:
        _add_symbols_with_source(
            sources,
            "etf_holding",
            get_universe_from_etf_fallback(profile.get("sector"), limit_holdings=20),
        )

    sources.pop(profile.get("symbol"), None)
    return profile, sources


# =============================================================================
# SCORING
# =============================================================================

def _candidate_is_eligible(target_profile: Dict[str, Any], candidate_profile: Dict[str, Any]) -> bool:
    """
    Precision-first filter. We would rather return fewer peers than pollute
    downstream benchmarking with weak matches.
    """
    symbol = candidate_profile.get("symbol")
    if not symbol or symbol == target_profile.get("symbol"):
        return False

    if not _is_common_stock_symbol(symbol):
        return False

    if _issuer_key(candidate_profile) == _issuer_key(target_profile):
        return False

    if str(candidate_profile.get("quote_type") or "").upper() != "EQUITY":
        return False

    target_sector_key = target_profile.get("sector_key")
    candidate_sector_key = candidate_profile.get("sector_key")
    if target_sector_key and candidate_sector_key and target_sector_key != candidate_sector_key:
        return False

    target_exchange = target_profile.get("exchange")
    candidate_exchange = candidate_profile.get("exchange")
    if _contains_disallowed_exchange(candidate_exchange) and not _contains_disallowed_exchange(target_exchange):
        return False

    market_cap_ratio = _ratio_band(target_profile.get("market_cap"), candidate_profile.get("market_cap"))
    if market_cap_ratio is not None and market_cap_ratio > MAX_SIZE_RATIO:
        return False

    revenue_ratio = _ratio_band(target_profile.get("revenue"), candidate_profile.get("revenue"))
    if market_cap_ratio is None and revenue_ratio is not None and revenue_ratio > MAX_SIZE_RATIO:
        return False

    target_industry_key = target_profile.get("industry_key")
    candidate_industry_key = candidate_profile.get("industry_key")
    exact_industry_match = (
        bool(target_industry_key)
        and bool(candidate_industry_key)
        and target_industry_key == candidate_industry_key
    )

    industry_similarity = _jaccard_similarity(
        target_profile.get("industry_tokens", set()),
        candidate_profile.get("industry_tokens", set()),
    )
    business_similarity = _jaccard_similarity(
        target_profile.get("business_tokens", set()),
        candidate_profile.get("business_tokens", set()),
    )
    target_structured = _profile_structured_features(target_profile)
    candidate_structured = _profile_structured_features(candidate_profile)
    industry_tag_similarity = _phrase_similarity(
        target_structured.get("industry_tags", []),
        candidate_structured.get("industry_tags", []),
    )
    core_keyword_similarity = _phrase_similarity(
        target_structured.get("core_keywords", []),
        candidate_structured.get("core_keywords", []),
    )
    business_model_similarity = _phrase_similarity(
        target_structured.get("business_model", []),
        candidate_structured.get("business_model", []),
    )
    negative_conflict = max(
        _negative_overlap(target_structured.get("negative_keywords", []), _positive_feature_phrases(candidate_profile)),
        _negative_overlap(candidate_structured.get("negative_keywords", []), _positive_feature_phrases(target_profile)),
    )

    if (
        negative_conflict >= 0.18
        and not exact_industry_match
        and industry_tag_similarity < 0.34
        and business_model_similarity < 0.50
    ):
        return False

    return (
        exact_industry_match
        or industry_similarity >= 0.20
        or industry_tag_similarity >= 0.34
        or business_model_similarity >= 0.50
        or core_keyword_similarity >= 0.18
        or business_similarity >= 0.10
    )


def score_peer(
    target_profile: Dict[str, Any],
    candidate_profile: Dict[str, Any],
    candidate_sources: Set[str],
) -> float:
    """
    Composite peer score built from business similarity, size similarity, and
    source confidence. Historical return similarity was removed because it was
    noisy, slow, and not a reliable proxy for peer quality.
    """
    score = 0.0

    target_industry_key = target_profile.get("industry_key")
    candidate_industry_key = candidate_profile.get("industry_key")
    if target_industry_key and candidate_industry_key and target_industry_key == candidate_industry_key:
        score += 45.0

    target_sector_key = target_profile.get("sector_key")
    candidate_sector_key = candidate_profile.get("sector_key")
    if target_sector_key and candidate_sector_key and target_sector_key == candidate_sector_key:
        score += 12.0

    industry_similarity = _jaccard_similarity(
        target_profile.get("industry_tokens", set()),
        candidate_profile.get("industry_tokens", set()),
    )
    business_similarity = _jaccard_similarity(
        target_profile.get("business_tokens", set()),
        candidate_profile.get("business_tokens", set()),
    )
    score += 18.0 * industry_similarity
    score += 10.0 * business_similarity

    target_structured = _profile_structured_features(target_profile)
    candidate_structured = _profile_structured_features(candidate_profile)
    industry_tag_similarity = _phrase_similarity(
        target_structured.get("industry_tags", []),
        candidate_structured.get("industry_tags", []),
    )
    business_model_similarity = _phrase_similarity(
        target_structured.get("business_model", []),
        candidate_structured.get("business_model", []),
    )
    revenue_driver_similarity = _phrase_similarity(
        target_structured.get("revenue_drivers", []),
        candidate_structured.get("revenue_drivers", []),
    )
    core_keyword_similarity = _phrase_similarity(
        target_structured.get("core_keywords", []),
        candidate_structured.get("core_keywords", []),
    )
    secondary_keyword_similarity = _phrase_similarity(
        target_structured.get("secondary_keywords", []),
        candidate_structured.get("secondary_keywords", []),
    )
    negative_conflict = max(
        _negative_overlap(target_structured.get("negative_keywords", []), _positive_feature_phrases(candidate_profile)),
        _negative_overlap(candidate_structured.get("negative_keywords", []), _positive_feature_phrases(target_profile)),
    )

    score += 12.0 * industry_tag_similarity
    score += 10.0 * business_model_similarity
    score += 7.0 * core_keyword_similarity
    score += 4.0 * secondary_keyword_similarity
    score += 4.0 * revenue_driver_similarity
    score -= 10.0 * negative_conflict

    score += 8.0 * _log_similarity(target_profile.get("market_cap"), candidate_profile.get("market_cap"))
    score += 6.0 * _log_similarity(target_profile.get("revenue"), candidate_profile.get("revenue"))

    score += 5.0 * _bounded_similarity(
        target_profile.get("operating_margin"),
        candidate_profile.get("operating_margin"),
        0.20,
    )
    score += 4.0 * _bounded_similarity(
        target_profile.get("gross_margin"),
        candidate_profile.get("gross_margin"),
        0.25,
    )
    score += 2.0 * _bounded_similarity(
        target_profile.get("beta"),
        candidate_profile.get("beta"),
        0.75,
    )

    if target_profile.get("country") and candidate_profile.get("country"):
        if target_profile.get("country") == candidate_profile.get("country"):
            score += 2.0

    if target_profile.get("currency") and candidate_profile.get("currency"):
        if target_profile.get("currency") == candidate_profile.get("currency"):
            score += 2.0

    if target_profile.get("exchange") and candidate_profile.get("exchange"):
        if target_profile.get("exchange") == candidate_profile.get("exchange"):
            score += 1.0

    score += sum(SOURCE_WEIGHTS.get(source, 0.0) for source in candidate_sources)
    return score


def _evaluate_candidate(
    target_profile: Dict[str, Any],
    symbol: str,
    candidate_sources: Set[str],
) -> Optional[Tuple[str, float, Dict[str, Any]]]:
    try:
        candidate_profile = get_company_profile(symbol)
        if not _candidate_is_eligible(target_profile, candidate_profile):
            return None

        score = score_peer(target_profile, candidate_profile, candidate_sources)
        return symbol, score, candidate_profile
    except Exception:
        return None


def get_top_peers(ticker: str, top_n: int = 10, return_period: str = "1y") -> List[str]:
    """
    Returns the best peer list available for the ticker.
    """
    _ = return_period  # Backward compatibility; return-based scoring was removed.

    ticker = _clean_symbol(ticker)
    if not ticker:
        return []

    print(f"Fetching peer universe for {ticker}...", flush=True)
    target_profile, candidate_sources = build_peer_universe(ticker)

    if not target_profile.get("sector_key") and not target_profile.get("industry_key"):
        print("Sector/industry information not available for this ticker.", flush=True)
        return []

    if not candidate_sources:
        print("No peer universe found from sector/industry data.", flush=True)
        return []

    max_workers = max(1, min(MAX_WORKERS, len(candidate_sources)))
    print(
        f"Evaluating {len(candidate_sources)} potential peers with up to {max_workers} workers...",
        flush=True,
    )

    scored: List[Tuple[str, float, Dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_evaluate_candidate, target_profile, symbol, sources): symbol
            for symbol, sources in candidate_sources.items()
        }
        for future in as_completed(future_map):
            result = future.result()
            if result is not None:
                scored.append(result)

    if not scored:
        print("No high-confidence peer candidates survived filtering.", flush=True)
        return []

    scored.sort(key=lambda item: item[1], reverse=True)
    best_score = scored[0][1]
    primary_floor = max(MINIMUM_PEER_SCORE, best_score * PRIMARY_SCORE_RATIO)
    relaxed_floor = max(RELAXED_MINIMUM_PEER_SCORE, best_score * RELAXED_SCORE_RATIO)

    result: List[str] = []
    seen_symbols: Set[str] = set()
    seen_issuers: Set[str] = {_issuer_key(target_profile)}

    # First pass keeps only the strongest matches. If that leaves us too few
    # names, we relax slightly, but we still refuse to pad with weak candidates.
    for score_floor in (primary_floor, relaxed_floor):
        for symbol, score, candidate_profile in scored:
            if len(result) >= top_n:
                break

            if score < score_floor:
                continue

            issuer_key = _issuer_key(candidate_profile)
            if symbol in seen_symbols or issuer_key in seen_issuers:
                continue

            seen_symbols.add(symbol)
            seen_issuers.add(issuer_key)
            result.append(symbol)

        if len(result) >= min(top_n, 5):
            break

    print(
        "Target profile:",
        {
            "sector": target_profile.get("sector"),
            "industry": target_profile.get("industry"),
            "sector_key": target_profile.get("sector_key"),
            "industry_key": target_profile.get("industry_key"),
        },
        flush=True,
    )
    print(
        f"Selected {len(result)} high-confidence peers from {len(scored)} eligible candidates.",
        flush=True,
    )
    print("Top peers:", result, flush=True)

    return result
