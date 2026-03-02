# SPDX-FileCopyrightText: 2025 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

import os


def get_apikey(name: str) -> str:
    key = os.getenv(name)
    if not key and (path := os.getenv(f"{name}_FILE")):
        with open(path, "r") as f:
            key = f.read()

    if not key:
        raise ValueError(f"{name} environment variable not set")

    return key.strip()
