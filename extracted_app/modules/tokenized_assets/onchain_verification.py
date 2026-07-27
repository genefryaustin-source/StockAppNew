"""
modules/tokenized_assets/onchain_verification.py

Independent on-chain cross-check for tokenized asset holdings, via web3.py
(https://github.com/ethereum/web3.py, MIT license). Every tokenized asset
broker in this package (Ondo, Securitize, custom) reports positions
through the custodian's own API -- this module lets the Risk Layer verify
a reported balance against the actual token contract on-chain instead of
trusting the custodian's report on faith. That distinction matters most
for the newest, least-battle-tested part of this app.

Uses public RPC endpoints by default (no API key required to get started),
overridable per chain via Admin > API Keys for a private/paid RPC
(Infura, Alchemy, etc.) if you want higher reliability than a public node.
"""

from __future__ import annotations

from typing import Optional
from web3 import Web3

# Public, no-signup-required RPC endpoints as a sane default. Override any
# of these per-tenant with a CHAIN_RPC_URL_<CHAIN> provider key (e.g.
# CHAIN_RPC_URL_ETHEREUM) if you have a paid/private RPC you'd rather use.
DEFAULT_PUBLIC_RPCS = {
    "ethereum": "https://eth.llamarpc.com",
    "polygon": "https://polygon-rpc.com",
    "arbitrum": "https://arb1.arbitrum.io/rpc",
    "optimism": "https://mainnet.optimism.io",
    "avalanche": "https://api.avax.network/ext/bc/C/rpc",
    "bnb chain": "https://bsc-dataseed.binance.org",
    "base": "https://mainnet.base.org",
}

_ERC20_MIN_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
     "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals",
     "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
]


def _resolve_rpc_url(chain: str, db=None, tenant_id: Optional[str] = None) -> Optional[str]:
    from modules.admin.tenant_api_keys import get_provider_key
    chain_key = chain.strip().lower()
    override = get_provider_key(f"CHAIN_RPC_URL_{chain_key.upper().replace(' ', '_')}", db=db, tenant_id=tenant_id)
    return override or DEFAULT_PUBLIC_RPCS.get(chain_key)


def get_erc20_balance(
    contract_address: str,
    wallet_address: str,
    chain: str = "ethereum",
    db=None,
    tenant_id: Optional[str] = None,
) -> dict:
    """Reads a token balance directly from the chain. Returns
    {"available": False, "reason": ...} on any failure (bad RPC, invalid
    address, contract doesn't implement the standard ERC-20 read methods)
    rather than raising."""
    rpc_url = _resolve_rpc_url(chain, db=db, tenant_id=tenant_id)
    if not rpc_url:
        return {"available": False, "reason": f"No RPC endpoint known for chain {chain!r}."}

    if not Web3.is_address(contract_address) or not Web3.is_address(wallet_address):
        return {"available": False, "reason": "Invalid contract or wallet address."}

    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
        if not w3.is_connected():
            return {"available": False, "reason": f"Could not connect to {chain} RPC ({rpc_url})."}

        contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=_ERC20_MIN_ABI)
        raw_balance = contract.functions.balanceOf(Web3.to_checksum_address(wallet_address)).call()
        decimals = contract.functions.decimals().call()
        balance = raw_balance / (10 ** decimals)

        return {
            "available": True, "chain": chain, "contract_address": contract_address,
            "wallet_address": wallet_address, "balance": balance, "decimals": decimals,
            "raw_balance": raw_balance,
        }
    except Exception as e:
        return {"available": False, "reason": f"On-chain balance read failed: {e}"}


def verify_position_onchain(
    contract_address: str,
    wallet_address: str,
    expected_qty: float,
    chain: str = "ethereum",
    tolerance_pct: float = 1.0,
    db=None,
    tenant_id: Optional[str] = None,
) -> dict:
    """
    Compares a custodian-reported quantity against the actual on-chain
    balance. tolerance_pct allows for small discrepancies (e.g. a pending
    settlement) before flagging a mismatch as suspicious.
    """
    onchain = get_erc20_balance(contract_address, wallet_address, chain=chain, db=db, tenant_id=tenant_id)
    if not onchain.get("available"):
        return {"available": False, "reason": onchain.get("reason"), "verified": False}

    onchain_qty = onchain["balance"]
    if expected_qty == 0:
        diff_pct = 0.0 if onchain_qty == 0 else float("inf")
    else:
        diff_pct = abs(onchain_qty - expected_qty) / abs(expected_qty) * 100.0

    matches = diff_pct <= tolerance_pct
    return {
        "available": True,
        "verified": matches,
        "expected_qty": expected_qty,
        "onchain_qty": onchain_qty,
        "difference_pct": diff_pct,
        "tolerance_pct": tolerance_pct,
        "chain": chain,
        "note": None if matches else (
            f"Custodian-reported quantity ({expected_qty}) differs from on-chain balance "
            f"({onchain_qty}) by {diff_pct:.2f}%, outside the {tolerance_pct}% tolerance."
        ),
    }
