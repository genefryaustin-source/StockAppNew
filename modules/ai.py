import os
import json

def ai_enabled() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))

def _client():
    from openai import OpenAI
    return OpenAI()

def ai_generate_memo(symbol, profile, fin_health, valuation, peer_table, tech, risks, summary_text) -> str:
    """
    Generates a memo using only the computed facts.
    We instruct the model: no speculation, no new facts, cite only from provided context.
    """
    client = _client()

    context = {
        "symbol": symbol,
        "profile": {k: profile.get(k) for k in ["longName", "sector", "industry", "marketCap", "website"]},
        "financial_health": fin_health,
        "valuation": valuation,
        "peers_sample": peer_table.head(10).to_dict(orient="records"),
        "technicals": tech,
        "risks": risks,
        "facts_summary_markdown": summary_text
    }

    sys = (
        "You are a senior equity research analyst. "
        "Write a concise investment memo strictly using the provided JSON facts only. "
        "Do NOT add any external facts. Do NOT speculate about events. "
        "If something is missing, say it is unavailable. "
        "Provide: thesis, key positives, key negatives, valuation view vs peers, and technical context."
    )

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": json.dumps(context)}
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content

def ai_qa(question: str, report_text: str) -> str:
    client = _client()
    sys = (
        "Answer questions strictly based on the report text provided. "
        "If the answer isn't in the report, say you don't have enough information."
    )
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": f"REPORT:\n{report_text}\n\nQUESTION:\n{question}"}
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content