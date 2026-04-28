import askgen as ask


def main():
    auth_file = "auth/local.json"
    auth = ask.Auth.read(auth_file)

    client = ask.Askcos(auth)
    token = client.login()
    print(token)

    client.logout()


if __name__ == "__main__":
    main()
