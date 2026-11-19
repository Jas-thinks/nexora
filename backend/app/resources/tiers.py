"""OUR editorial grouping of companies. This is NOT sourced compensation data: pay varies by role, location and year.
'service' = large IT-services / mass recruiters, where entry-level offers are commonly (not always) below ~10 LPA in India; verify per offer."""
import re

TIER_LABELS = {
    "faang": "FAANG / MAANG",
    "bigtech": "Big tech",
    "product": "Product & unicorns (India)",
    "finance": "Finance & quant",
    "service": "Service-based & mass recruiters",
    "other": "Other companies",
}
FAANG = {"meta", "apple", "amazon", "netflix", "google", "microsoft"}
BIGTECH = {"adobe", "oracle", "salesforce", "uber", "airbnb", "linkedin", "nvidia", "intel", "cisco", "sap", "vmware", "atlassian", "stripe", "snowflake", "databricks", "tesla", "qualcomm",
           "samsung", "intuit", "paypal", "servicenow", "walmart labs", "twilio", "dropbox", "pinterest", "snap", "spotify", "lyft", "doordash", "coinbase", "openai", "shopify", "bloomberg",
           "visa", "mastercard", "ebay", "expedia", "booking.com", "palo alto networks", "workday", "square", "block", "cloudflare", "datadog", "roblox", "tiktok", "bytedance", "amd", "arista networks"}
PRODUCT = {"flipkart", "swiggy", "zomato", "paytm", "phonepe", "cred", "razorpay", "meesho", "myntra", "ola cabs", "dream11", "sharechat", "groww", "zoho", "freshworks", "inmobi", "directi",
           "makemytrip", "nykaa", "urban company", "cars24", "curefit", "delhivery", "juspay", "cashfree", "slice", "navi", "bharatpe", "hotstar", "lenskart", "dunzo", "info edge", "mindtickle",
           "moengage", "sprinklr", "hashedin", "media.net", "pubmatic", "hiver", "darwinbox", "airtel", "freecharge", "payu", "snapdeal", "licious", "ninjacart", "winzo", "gameskraft"}
FINANCE = {"goldman sachs", "morgan stanley", "j.p. morgan", "de shaw", "jane street", "citadel", "two sigma", "american express", "bank of america", "barclays", "deutsche bank", "hsbc",
           "citigroup", "wells fargo", "ubs", "blackrock", "arcesium", "optiver", "tower research capital", "hudson river trading", "jump trading", "bny mellon", "fidelity", "capital one", "rbc"}
SERVICE = {"tcs", "infosys", "wipro", "cognizant", "accenture", "capgemini", "hcl", "tech mahindra", "lti", "mindtree", "genpact", "dxc technology", "deloitte", "ey", "pwc", "virtusa",
           "coforge", "nagarro", "persistent", "persistent systems", "publicis sapient", "epam systems", "luxoft", "altimetrik", "mphasis", "hexaware", "zensar", "birlasoft", "ltimindtree", "cognizant technology solutions",
           "larsen & toubro", "qburst", "thoughtworks", "sigmoid", "tiger analytics", "maq software", "cedcoss", "mountblue", "accolite", "ibm", "dell", "hp", "hpe", "ncr", "amdocs", "optum", "ge digital"}
DOMAINS = {  # editorial: which design questions are good practice for this company's domain (not reported interview data)
    "amazon": "ecommerce", "flipkart": "ecommerce", "myntra": "ecommerce", "meesho": "ecommerce", "walmart labs": "ecommerce", "nykaa": "ecommerce", "ebay": "ecommerce",
    "google": "search", "microsoft": "cloud", "meta": "social", "linkedin": "social", "snap": "social", "pinterest": "social", "sharechat": "social",
    "netflix": "streaming", "hotstar": "streaming", "spotify": "streaming", "uber": "mobility", "ola cabs": "mobility", "lyft": "mobility", "swiggy": "delivery", "zomato": "delivery", "doordash": "delivery",
    "paytm": "payments", "phonepe": "payments", "razorpay": "payments", "paypal": "payments", "stripe": "payments", "cred": "payments", "visa": "payments", "mastercard": "payments",
    "dropbox": "storage", "oracle": "cloud", "salesforce": "cloud", "atlassian": "collab", "adobe": "collab", "zoho": "collab",
}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def tier_of(name: str) -> str:
    n = name.strip().lower()
    for tier, group in (("faang", FAANG), ("bigtech", BIGTECH), ("product", PRODUCT), ("finance", FINANCE), ("service", SERVICE)):
        if n in group:
            return tier
    return "other"


_ACRONYMS = {"tcs": "TCS", "oyo": "OYO", "ibm": "IBM", "hcl": "HCL", "lti": "LTI", "jio": "Jio"}


def display_name(name: str) -> str:
    """Source folders are occasionally all-lowercase ('tcs', 'razorpay'); show them properly without touching already-cased names."""
    n = name.strip()
    return _ACRONYMS.get(n.lower(), n.title() if n == n.lower() else n)
