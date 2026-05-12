import olca_ipc as ipc
import olca_schema as o

from retrolca import oipc
from retrolca.res import unwrap


def main():
    client = ipc.Client()
    ctx, _ = oipc.IpcContext.of(client)
    assert ctx
    providers = oipc.ProviderIndex.of(ctx)
    for smiles, provider in providers.data.items():
        print(f"{smiles} --> {name_of(provider)}")


def name_of(provider: o.TechFlow) -> str:
    p = unwrap(provider.provider)
    name = unwrap(p.name)
    if p.location:
        name += " - " + p.location
    return name


if __name__ == "__main__":
    main()
