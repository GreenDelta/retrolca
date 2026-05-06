import datetime
import time

import olca_ipc as ipc
import olca_schema as o

from askgen import pubchem, oipc, smiles


def main():
    client = ipc.Client()
    ctx, err = oipc.Context.of(client)
    if err:
        print(f"Failed to load context: {err}")
        return

    flows: list[o.Flow] = []
    for flow in client.get_all(o.Flow):
        if should_try(ctx, flow):
            flows.append(flow)

    n = len(flows)
    if n == 0:
        print("No untagged chemical products found")
        return
    print(f"Found {n} chemical products to test")

    i = 0
    for flow in flows:
        i += 1
        # try to add attributes from PubChem
        print(f"{flow.name} ({flow.id}) ... [{i}/{n}]")
        b = pubchem.decorate_flow(ctx, flow)
        if b:
            print("  ... updated")
        else:
            print("  ... not found on PubChem")

        # mark the flow as checked and update it
        if not flow.other_properties:
            flow.other_properties = {}
        timestamp = datetime.datetime.now().isoformat()
        flow.other_properties["PubChem-Check"] = timestamp
        flow.last_change = timestamp
        flow.version = increment_version(flow.version)
        client.put(flow)

        time.sleep(0.3)


def should_try(ctx: oipc.Context, flow: o.Flow) -> bool:
    # only try product flows with a category and name given
    if not flow or flow.flow_type != o.FlowType.PRODUCT_FLOW:
        return False
    if not flow.category or not flow.name:
        return False

    # we identify chemicals by their category
    path = flow.category.lower()
    if "manufacture of basic chemicals" not in path:
        return False

    # check if the flow is already suitable for retrosynthesis
    code = smiles.of_flow(flow)
    mm = ctx.molar_mass_of(flow)
    if code and mm:
        return False

    # ignore when the flow was already checked
    if flow.other_properties:
        state = flow.other_properties.get("PubChem-Check")
        if state:
            return False

    # mass has to be the reference flow property
    mass_prop = ctx.mass_prop_of(flow)
    if not mass_prop or not mass_prop.is_ref_flow_property:
        return False

    return True


def increment_version(v: str | None) -> str:
    if not v:
        return "0.0.1"
    parts = []
    for si in v.split("."):
        vi = si.strip()
        if vi == "":
            parts.append(0)
        else:
            parts.append(int(vi))
    if len(parts) == 0:
        return "0.0.1"
    parts[-1] = parts[-1] + 1
    return ".".join([str(i) for i in parts])


if __name__ == "__main__":
    main()
