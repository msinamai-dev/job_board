import logging
import requests
from functools import lru_cache

logger = logging.getLogger(__name__)


# ================================================================
# CONFIGURATION
# ================================================================

ESCO_API_URL = "https://ec.europa.eu/esco/api"

ESCO_VERSION = "1.2.1"

LANGUAGE = "en"

REQUEST_TIMEOUT = 10


def normalize_text(value):
    if not value:
        return ""

    value = str(value).strip().lower()

    return " ".join(value.split())


def _api_get(endpoint, params=None):
    """
    Make a GET request to ESCO.

    ESCO is an external service, so failure must never break
    the Django job matching system.
    """

    try:
        response = requests.get(
            f"{ESCO_API_URL.rstrip('/')}/{endpoint.lstrip('/')}",
            params=params,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as exc:

        logger.warning(
            "[ESCO] API request failed: %s",
            exc
        )

        return None

    except ValueError as exc:

        logger.warning(
            "[ESCO] Invalid JSON response: %s",
            exc
        )

        return None


@lru_cache(maxsize=500)
def search_concepts(text):
    """
    Search ESCO for a job title or skill.

    Returns a list of ESCO search results.

    The cache here prevents repeatedly searching ESCO for
    exactly the same text during the lifetime of the process.
    """

    text = normalize_text(text)

    if not text:
        return []

    logger.info(
        "[ESCO] Searching: %s",
        text
    )

    data = _api_get(
        "search",
        params={
            "text": text,
            "language": LANGUAGE,
            "selectedVersion": ESCO_VERSION,
            "type": "occupation",
            "limit": 10,
        },
    )

    if not data:
        return []

    results = []

    # ESCO response structures can differ between API versions.
    raw_results = (
        data.get("_embedded", {}).get("results", [])
        if isinstance(data, dict)
        else []
    )

    for item in raw_results:

        if not isinstance(item, dict):
            continue

        uri = (
            item.get("uri")
            or item.get("conceptUri")
            or item.get("id")
        )

        title = (
            item.get("preferredLabel")
            or item.get("title")
            or item.get("label")
            or ""
        )

        description = (
            item.get("description")
            or ""
        )

        if uri or title:

            results.append({
                "uri": uri,
                "title": normalize_text(title),
                "description": normalize_text(description),
            })

    logger.info(
        "[ESCO] Search '%s' returned %d result(s)",
        text,
        len(results)
    )

    return results


# ================================================================
# GET CONCEPT
# ================================================================

@lru_cache(maxsize=500)
def get_concept(uri):
    """
    Retrieve detailed information about an ESCO concept.
    """

    if not uri:
        return None

    logger.info(
        "[ESCO] Loading concept: %s",
        uri
    )

    # ESCO accepts concept URIs.
    encoded_uri = requests.utils.quote(
        uri,
        safe=""
    )

    data = _api_get(
        "resource",
        params={
            "uri": uri,
            "language": LANGUAGE,
            "selectedVersion": ESCO_VERSION,
        },
    )

    if data:
        return data

    return None


# ================================================================
# GET RELATED LABELS
# ================================================================

def get_related_labels(text):
    """
    Backwards-compatible helper used by the existing matching code.

    Returns labels associated with the best ESCO occupation matches.
    """

    text = normalize_text(text)

    if not text:
        return set()

    results = search_concepts(text)

    labels = set()

    for result in results:

        title = normalize_text(
            result.get("title", "")
        )

        if title:
            labels.add(title)

    return labels


# ================================================================
# OCCUPATION PROFILE
# ================================================================

def get_occupation_profile(text):
    """
    Return a richer ESCO representation of a job title.

    This is what the new matching engine should use.
    """

    text = normalize_text(text)

    if not text:
        return {
            "query": "",
            "occupations": [],
            "labels": set(),
            "descriptions": set(),
        }

    results = search_concepts(text)

    labels = set()
    descriptions = set()
    occupations = []

    for result in results:

        title = normalize_text(
            result.get("title", "")
        )

        description = normalize_text(
            result.get("description", "")
        )

        if title:
            labels.add(title)

        if description:
            descriptions.add(description)

        occupations.append({
            "uri": result.get("uri"),
            "title": title,
            "description": description,
        })

    return {
        "query": text,
        "occupations": occupations,
        "labels": labels,
        "descriptions": descriptions,
    }


# ================================================================
# CLEAR CACHE
# ================================================================

def clear_cache():
    """
    Clear the in-memory ESCO API search cache.

    Useful during development/testing.
    """

    search_concepts.cache_clear()
    get_concept.cache_clear()