def compare_with_peers(company_metrics, peer_metrics_list):
    comparison = {}

    for key, company_value in company_metrics["valuation"].items():
        peer_values = [
            peer["valuation"].get(key)
            for peer in peer_metrics_list
            if peer["valuation"].get(key) is not None
        ]

        comparison[key] = {
            "company": company_value,
            "peer_avg": sum(peer_values) / len(peer_values) if peer_values else None,
        }

    return comparison
