import  askgen.zynth as z

config = z.ZynthConfig.from_file("auth/local-zynth.json")
client = z.ZynthClient(config)
reactions = client.expand("C([C@@H]1[C@@H]([C@@H]([C@H]([C@H](O1)O[C@]2([C@H]([C@@H]([C@H](O2)CCl)O)O)CCl)O)O)Cl)O")

for r in reactions:
    print(r)
