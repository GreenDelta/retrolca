import olca_ipc as ipc
import olca_schema as o


from askgen import oipc, smiles


def main():
    client = ipc.Client()
    ctx, _ = oipc.Context.load(client)
    for flow in client.get_all(o.Flow):
        smiles_code = smiles.of_flow(flow)
        mm = ctx.molar_mass_of(flow)
        if not smiles_code or not mm:
            continue

        score = 0
        provider: o.TechFlow | None = None
        for p in client.get_providers(flow):
            if not provider:
                provider = p
                score = provider_score_of(p)
                continue
            s = provider_score_of(p)
            if s > score:
                provider = p
                score = s

        print(flow.name)
        if provider:
            name = provider.provider.name
            if provider.provider.location:
                name += " - " + provider.provider.location
            print(f"  -> {name} ({score})")
        else:
            print("  -> NONE")


def provider_score_of(p: o.TechFlow, location="GLO") -> float:
    if not p or not p.flow or not p.provider:
        return 0.0
    score = 0.0
    if p.flow.name and p.provider.name:
        market_prefix = "market for " + p.flow.name
        prod_prefix = p.flow.name + " production"
        if p.provider.name.startswith(market_prefix):
            score += 8
        elif p.provider.name.startswith(prod_prefix):
            score += 5

    if p.provider.location:
        if p.provider.location == location:
            score += 10
        elif p.provider.location == "GLO":
            score += 5
        elif p.provider.location == "RoW":
            score += 2
    return score


if __name__ == "__main__":
    main()
