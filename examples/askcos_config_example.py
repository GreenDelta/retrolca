from pathlib import Path

import retrolca as r


def main():
    root = Path(__file__).parent.parent

    login = r.AskcosLogin.from_file(root / "auth/remote-askcos.json")
    tool = r.AskcosClient(
        login,
        options={
            "retro_backend_options": [
                {
                    "retro_backend": "template_relevance",
                    "retro_model_name": "reaxys",
                    "max_num_templates": 1000,
                    "max_cum_prob": 0.995,
                    "attribute_filter": [],
                    "threshold": 0.3,
                    "top_k": 10,
                }
            ],
            "banned_chemicals": [],
            "banned_reactions": [],
            "use_fast_filter": True,
            "fast_filter_threshold": 0.75,
            "retro_rerank_backend": "relevance_heuristic",
            "atom_map_backend": "rxnmapper",
            "cluster_precursors": False,
            "cluster_setting": {
                "feature": "original",
                "cluster_method": "hdbscan",
                "fp_type": "morgan",
                "fp_length": 512,
                "fp_radius": 1,
                "classification_threshold": 0.2,
            },
            "extract_template": False,
            "return_reacting_atoms": True,
            "selectivity_check": False,
        },
    )

    reactions, err = tool.expand("CCOP(=O)(OCC)OCC")
    if err or not reactions:
        print("Query failed: ", err)
        return

    for rc in reactions:
        print(f"score: {rc.score} feasibility:{rc.feasibility} :: {rc.smiles}")

    tool.close()


if __name__ == "__main__":
    main()
