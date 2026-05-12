from typing import Any


def _request_of(smiles_code: str, model="pistachio") -> dict[str, Any]:
    return {
        "smiles": smiles_code,
        "retro_backend_options": [
            {
                "retro_backend": "template_relevance",
                "max_num_templates": 1000,
                "max_cum_prob": 0.999,
                "retro_model_name": "pistachio",
            }
        ],
        "retro_rerank_backend": "relevance_heuristic",
        "atom_map_backend": "rxnmapper",
        "use_fast_filter": True,
        "fast_filter_threshold": 0.1,
        "cluster_precursors": False,
    }


def main():
    print(_request_of("C1CC(=O)N(C1)CCO"))


if __name__ == "__main__":
    main()
