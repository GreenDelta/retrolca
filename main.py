import logging

import askgen as ask


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    auth_file = "auth/local.json"
    auth = ask.Auth.read(auth_file)

    client = ask.Askcos(auth)
    token = client.login()
    print(token)

    client.logout()


if __name__ == "__main__":
    main()
