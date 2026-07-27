"""
modules/crypto/crypto_sanctions_service.py

Sprint CR-1: Autonomous Wallet Intelligence -- sanctions data source.

Fetches and parses OFAC's own official "Advanced XML" export of the
Specially Designated Nationals (SDN) list, extracting the digital
currency addresses it publishes directly -- no API key, no
third-party service, free and official.

XML traversal structure below matches the OFAC Advanced XML schema
exactly (namespace URI, FeatureTypeID lookup via
ReferenceValueSets/FeatureTypeValues, address values via
DistinctParties//*[@FeatureTypeID]/VersionDetail) -- verified against
a real, working reference implementation
(0xB10C/ofac-sanctioned-digital-currency-addresses) rather than
guessed from the schema name alone.

NOTE: the source XML is tens of MB (OFAC's own docs describe it as
~80MB), and treasury.gov is outside this sandbox's allowed fetch
domains, so the live fetch itself cannot be executed or verified from
here. The parsing logic is built to the exact, confirmed schema and
is unit-testable against a realistic, hand-built sample independent
of network access; the live end-to-end fetch needs to be verified in
the deployed environment, where outbound access to treasury.gov is
available.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

OFAC_SDN_ADVANCED_XML_URL = (
    "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/ADVANCED_XML"
)

_NAMESPACE = {
    "sdn": "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/ADVANCED_XML"
}

# Every digital-currency asset OFAC has published addresses for as of
# this writing. New assets show up as new "Digital Currency Address -
# <ASSET>" FeatureType entries in the XML itself; anything not in this
# list simply won't be found by _get_feature_type_id() and is safely
# skipped, not silently mis-parsed.
SUPPORTED_ASSETS = [
    "XBT", "ETH", "XMR", "LTC", "ZEC", "DASH", "BTG", "ETC",
    "BSV", "BCH", "XVG", "USDT", "XRP", "ARB", "BSC", "USDC",
    "TRX", "SOL",
]


def _feature_type_text(asset: str) -> str:
    return f"Digital Currency Address - {asset}"


def _get_feature_type_id(root: ET.Element, asset: str) -> Optional[str]:
    feature_type = root.find(
        f"sdn:ReferenceValueSets/sdn:FeatureTypeValues/*[.='{_feature_type_text(asset)}']",
        _NAMESPACE,
    )
    if feature_type is None:
        return None
    return feature_type.attrib.get("ID")


def _get_addresses_for_feature_type(root: ET.Element, feature_type_id: str) -> List[str]:
    addresses: List[str] = []
    for feature in root.findall(
        f"sdn:DistinctParties//*[@FeatureTypeID='{feature_type_id}']", _NAMESPACE,
    ):
        for version_detail in feature.findall(".//sdn:VersionDetail", _NAMESPACE):
            if version_detail.text:
                addresses.append(version_detail.text.strip())
    return addresses


def parse_sdn_advanced_xml(xml_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Parses a real OFAC Advanced XML payload into a flat list of
    {"address", "asset"} dicts, one per sanctioned digital currency
    address found, across every asset in SUPPORTED_ASSETS.

    Deliberately does not attempt to resolve entity_name/program here.
    Those live several XML hops away from the address feature itself
    (through separate Party/Profile/Sanctions-Program cross-reference
    structures) -- getting that wrong would risk mis-attributing which
    person/entity/program a given address belongs to, which matters a
    lot more for a sanctions list than an empty field does. The
    address itself -- the actual screening signal -- is extracted
    precisely and correctly; entity context can be added later once
    that cross-reference structure has been traced and verified with
    the same rigor.
    """
    root = ET.fromstring(xml_bytes)

    results: List[Dict[str, Any]] = []
    for asset in SUPPORTED_ASSETS:
        feature_type_id = _get_feature_type_id(root, asset)
        if feature_type_id is None:
            continue

        addresses = _get_addresses_for_feature_type(root, feature_type_id)
        # De-duplicate within this asset the same way the reference
        # tool does (dict.fromkeys preserves first-seen order).
        addresses = list(dict.fromkeys(addresses))

        for address in addresses:
            results.append({"address": address, "asset": asset, "program": None, "entity_name": None})

    return results


def fetch_and_parse_sdn_addresses() -> Dict[str, Any]:
    """
    Fetches the live OFAC Advanced XML export and parses it.

    Real network call to treasury.gov -- cannot be executed inside
    this sandbox (outside the allowed fetch domains), so this cannot
    be verified end-to-end from here. parse_sdn_advanced_xml() above
    is independently correct and testable against a realistic sample;
    this wrapper is a thin, low-risk fetch-then-parse shell around it.
    """
    try:
        import urllib.request

        req = urllib.request.Request(
            OFAC_SDN_ADVANCED_XML_URL,
            headers={"User-Agent": "Mozilla/5.0 (compatible; WalletIntelligence/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            xml_bytes = resp.read()

        rows = parse_sdn_advanced_xml(xml_bytes)
        return {"status": "ok", "rows": rows, "count": len(rows)}

    except Exception as exc:
        logger.warning("OFAC SDN fetch/parse failed: %s", exc)
        return {"status": "error", "message": str(exc), "rows": []}