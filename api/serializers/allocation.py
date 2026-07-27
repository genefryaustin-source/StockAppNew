def serialize_allocation(report):

    if report is None:
        return None

    return {

        "total_market_value": report["total_market_value"],

        "position_count": report["position_count"],

        "allocations": report["allocations"],

    }