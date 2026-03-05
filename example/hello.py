#!/usr/bin/env python3
"""A tiny sample script included to demonstrate non-markdown text packing."""


def greet(name: str = "world") -> str:
    return f"Hello, {name}!"


if __name__ == "__main__":
    print(greet())
