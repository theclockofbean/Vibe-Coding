from typing import List, Dict, Any


class CalibratedReranker:

    def __init__(self):
        self.weights = {
            "vector": 0.65,
            "token_overlap": 0.15,
            "char_overlap": 0.10,
            "domain": 0.07,
            "source_type": 0.03,
        }

        self.domain_boost = {
            "spec": 0.05,
            "logistics": 0.00,
            "price": -0.03,
            "quality": 0.02,
        }

    def _normalize(self, x: float) -> float:
        if x is None:
            return 0.0
        return max(0.0, min(1.0, float(x)))

    def score(self, query: str, item: Dict[str, Any], domain: str = None) -> float:

        vector_score = self._normalize(item.get("score", 0.0))

        token_overlap = item.get("token_overlap", 0.0)
        char_overlap = item.get("char_overlap", 0.0)

        domain_match = 1.0 if item.get("domain") == domain else 0.0
        source_type_score = item.get("source_type_score", 0.75)

        domain_boost = self.domain_boost.get(domain, 0.0)

        final_score = (
            self.weights["vector"] * vector_score +
            self.weights["token_overlap"] * token_overlap +
            self.weights["char_overlap"] * char_overlap +
            self.weights["domain"] * domain_match +
            self.weights["source_type"] * source_type_score +
            domain_boost
        )

        return max(0.0, min(1.0, final_score))

    def rerank(self, query: str, items: List[Dict[str, Any]], domain: str = None, top_k: int = 5):

        results = []

        for item in items:
            score = self.score(query, item, domain)
            results.append({**item, "calibrated_score": score})

        results.sort(key=lambda x: x["calibrated_score"], reverse=True)

        return results[:top_k]