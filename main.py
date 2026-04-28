import json
import logging

import askgen as ask


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    # auth_file = "auth/local.json"
    auth_file = "auth/remote.json"
    auth = ask.Auth.read(auth_file)

    client = ask.Client(auth)
    client.login()

    req = ask.RetroRequest.of("CCCCN1CCCC1=O")
    task_id = client.run(req)
    result = client.poll(task_id)

    with open(f"out/{task_id}.json", "w", encoding="utf-8") as f:
        json.dump(result, f)

    client.logout()


if __name__ == "__main__":
    main()
