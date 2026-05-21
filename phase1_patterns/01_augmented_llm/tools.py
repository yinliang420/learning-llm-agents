"""
Materials property mock database + tool implementations.

In production this would hit a real database or API.
The agent mechanics are identical — only this file changes.
"""

from __future__ import annotations

MATERIALS_DB: dict = {
    "steel": {
        "Young's modulus": {"value": 200,  "unit": "GPa"},
        "density":         {"value": 7850, "unit": "kg/m³"},
        "melting point":   {"value": 1370, "unit": "°C"},
        "hardness":        {"value": 130,  "unit": "HB"},
    },
    "aluminium": {
        "Young's modulus": {"value": 69,   "unit": "GPa"},
        "density":         {"value": 2700, "unit": "kg/m³"},
        "melting point":   {"value": 660,  "unit": "°C"},
        "hardness":        {"value": 25,   "unit": "HB"},
    },
    "SiC": {
        "Young's modulus": {"value": 410,  "unit": "GPa"},
        "density":         {"value": 3210, "unit": "kg/m³"},
        "melting point":   {"value": 2730, "unit": "°C"},
        "hardness":        {"value": 2500, "unit": "HV"},
    },
    "copper": {
        "Young's modulus": {"value": 110,  "unit": "GPa"},
        "density":         {"value": 8960, "unit": "kg/m³"},
        "melting point":   {"value": 1085, "unit": "°C"},
        "hardness":        {"value": 35,   "unit": "HB"},
    },
    "titanium": {
        "Young's modulus": {"value": 116,  "unit": "GPa"},
        "density":         {"value": 4500, "unit": "kg/m³"},
        "melting point":   {"value": 1668, "unit": "°C"},
        "hardness":        {"value": 70,   "unit": "HB"},
    },
}


def lookup_material_property(material: str, property: str) -> dict:
    mat_key = next((k for k in MATERIALS_DB if k.lower() == material.lower()), None)
    if mat_key is None:
        return {
            "found": False,
            "error": f"'{material}' not in database.",
            "available_materials": list(MATERIALS_DB.keys()),
        }

    prop_key = next((k for k in MATERIALS_DB[mat_key] if k.lower() == property.lower()), None)
    if prop_key is None:
        return {
            "found": False,
            "error": f"Property '{property}' not found for {mat_key}.",
            "available_properties": list(MATERIALS_DB[mat_key].keys()),
        }

    data = MATERIALS_DB[mat_key][prop_key]
    return {
        "found": True,
        "material": mat_key,
        "property": prop_key,
        "value": data["value"],
        "unit": data["unit"],
    }


def list_materials() -> dict:
    return {
        "materials": list(MATERIALS_DB.keys()),
        "queryable_properties": ["Young's modulus", "density", "melting point", "hardness"],
    }
