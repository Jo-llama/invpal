"""Builds deterministic master data (suppliers, construction companies,
Baustellen) using a seeded Faker("de_DE") instance.
"""

from __future__ import annotations

import random

from faker import Faker

from .catalogue import MATERIAL_CATALOGUE
from .models import Baustelle, ConstructionCompany, MasterData, Supplier

N_SUPPLIERS = 5
N_COMPANIES = 8
N_BAUSTELLEN = 15

SUPPLIER_SUFFIXES = ["Baustoffe GmbH", "Baustoffhandel GmbH", "Transportbeton GmbH & Co. KG", "Kies- und Sandwerke GmbH"]
COMPANY_SUFFIXES = ["Hochbau GmbH", "Tiefbau GmbH", "Bauunternehmung GmbH & Co. KG", "Bau AG"]
BAUSTELLE_PREFIXES = ["Neubau Wohnanlage", "Sanierung", "Neubau Gewerbepark", "Umbau", "Erweiterung", "Neubau Mehrfamilienhaus"]


def _vat_id(rng: random.Random) -> str:
    return "DE" + "".join(str(rng.randint(0, 9)) for _ in range(9))


def _build_suppliers(rng: random.Random, faker: Faker) -> list[Supplier]:
    suppliers = []
    for i in range(1, N_SUPPLIERS + 1):
        name = f"{faker.last_name()} {rng.choice(SUPPLIER_SUFFIXES)}"
        suppliers.append(
            Supplier(
                id=f"SUP-{i:02d}",
                name=name,
                street=faker.street_address(),
                zip_code=faker.postcode(),
                city=faker.city(),
                phone=faker.phone_number(),
                email=faker.company_email(),
                ust_id=_vat_id(rng),
            )
        )
    return suppliers


def _build_companies(rng: random.Random, faker: Faker) -> list[ConstructionCompany]:
    companies = []
    for i in range(1, N_COMPANIES + 1):
        name = f"{faker.last_name()} {rng.choice(COMPANY_SUFFIXES)}"
        companies.append(
            ConstructionCompany(
                id=f"CO-{i:02d}",
                name=name,
                street=faker.street_address(),
                zip_code=faker.postcode(),
                city=faker.city(),
                phone=faker.phone_number(),
                email=faker.company_email(),
            )
        )
    return companies


def _build_baustellen(rng: random.Random, faker: Faker, companies: list[ConstructionCompany]) -> list[Baustelle]:
    baustellen = []
    for i in range(1, N_BAUSTELLEN + 1):
        company = rng.choice(companies)
        street = faker.street_address()
        name = f"{rng.choice(BAUSTELLE_PREFIXES)} {street.split(' ')[0]}"
        baustellen.append(
            Baustelle(
                id=f"BS-{i:02d}",
                name=name,
                street=street,
                zip_code=faker.postcode(),
                city=faker.city(),
                company_id=company.id,
            )
        )
    return baustellen


def build_master_data(rng: random.Random, faker: Faker) -> MasterData:
    suppliers = _build_suppliers(rng, faker)
    companies = _build_companies(rng, faker)
    baustellen = _build_baustellen(rng, faker, companies)
    return MasterData(
        suppliers=suppliers,
        companies=companies,
        baustellen=baustellen,
        materials=list(MATERIAL_CATALOGUE),
    )
