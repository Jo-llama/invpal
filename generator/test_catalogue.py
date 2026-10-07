from .catalogue import MATERIAL_CATALOGUE
from .models import MaterialCategory, Unit

EXPECTED_UNIT_BY_CATEGORY = {
    MaterialCategory.SCHUETTGUT: Unit.TONNE,
    MaterialCategory.BETON: Unit.CUBIC_METER,
    MaterialCategory.ASPHALT: Unit.TONNE,
    MaterialCategory.STAHL: Unit.KILOGRAM,
    MaterialCategory.FERTIGTEIL: Unit.PIECE,
}


def test_catalogue_has_around_twenty_items():
    assert 18 <= len(MATERIAL_CATALOGUE) <= 22


def test_catalogue_ids_are_unique():
    ids = [item.id for item in MATERIAL_CATALOGUE]
    assert len(ids) == len(set(ids))


def test_each_category_present_with_expected_unit():
    categories_seen = {item.category for item in MATERIAL_CATALOGUE}
    assert categories_seen == set(EXPECTED_UNIT_BY_CATEGORY)
    for item in MATERIAL_CATALOGUE:
        assert item.unit == EXPECTED_UNIT_BY_CATEGORY[item.category]


def test_price_ranges_are_sane():
    for item in MATERIAL_CATALOGUE:
        assert 0 < item.price_min < item.price_max
