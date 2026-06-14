from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    DIRECTOR = "director"
    ACCOUNTANT = "accountant"
