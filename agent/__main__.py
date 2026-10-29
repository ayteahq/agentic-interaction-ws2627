"""Kommandozeileneinstieg für Exercise 1 (noch ohne API-Aufruf)."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Exercise 1 – First Tool Call")
    parser.add_argument("prompt", help="Die Anfrage an den Agenten")
    args = parser.parse_args()
    print(f"Testeingabe: {args.prompt}")


if __name__ == "__main__":
    main()
