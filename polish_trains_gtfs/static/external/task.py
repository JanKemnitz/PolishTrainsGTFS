# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

from abc import abstractmethod

from impuls import Resource, Task


class LoadExternal(Task):
    @staticmethod
    @abstractmethod
    def get_required_resources() -> dict[str, Resource]:
        raise NotImplementedError
