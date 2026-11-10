"""Small domain objects used by the Lost and Found application."""
from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: str
    name: str
    email: str

    def as_dict(self):
        return {"name": self.name, "email": self.email}


@dataclass(frozen=True)
class ItemReport:
    id: str
    name: str
    category: str
    color: str
    location: str
    description: str
    date: str
    owner: str
    status: str = "unrecovered"

    def as_dict(self):
        return {key: value for key, value in self.__dict__.items()}


@dataclass(frozen=True)
class ItemMatch:
    lost_id: str
    found_id: str
    verified: bool = False
    recovered: bool = False

    def as_dict(self):
        return {"lostId": self.lost_id, "foundId": self.found_id,
                "verified": self.verified, "recovered": self.recovered}
