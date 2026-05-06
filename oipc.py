import olca_ipc as ipc
import olca_schema as o

from askgen import oipc
from askgen.res import unwrap


def main():
    client = ipc.Client()
    ctx, _ = oipc.Context.of(client)
    providers = oipc.ProviderIndex.of(ctx)
    for provider, flow in providers.data.values():
        print(f"{flow.name} --> {name_of(provider)}")


def name_of(provider: o.TechFlow) -> str:
    p = unwrap(provider.provider)
    name = unwrap(p.name)
    if p.location:
        name += " - " + p.location
    return name


if __name__ == "__main__":
    main()
