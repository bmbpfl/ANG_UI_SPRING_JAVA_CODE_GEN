"""Name conversion utilities."""
import re


def to_pascal(name: str) -> str:
    """mas_investments -> MasInvestments"""
    return "".join(word.capitalize() for word in name.split("_"))


def to_camel(name: str) -> str:
    """mas_investments -> masInvestments"""
    parts = name.split("_")
    return parts[0].lower() + "".join(w.capitalize() for w in parts[1:])


def to_kebab(name: str) -> str:
    """mas_investments -> mas-investments"""
    return name.replace("_", "-")
