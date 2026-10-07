"""Hand-written material catalogue with realistic German construction-market
units and price ranges (EUR, ex-works, 2024 price level).
"""

from __future__ import annotations

from .models import MaterialCategory, MaterialItem, Unit

MATERIAL_CATALOGUE: list[MaterialItem] = [
    # Schüttgut (t)
    MaterialItem(id="MAT-01", name="Kies 0/4", unit=Unit.TONNE, category=MaterialCategory.SCHUETTGUT, price_min=9.0, price_max=14.0),
    MaterialItem(id="MAT-02", name="Kies 2/8", unit=Unit.TONNE, category=MaterialCategory.SCHUETTGUT, price_min=10.0, price_max=15.0),
    MaterialItem(id="MAT-03", name="Sand 0/2", unit=Unit.TONNE, category=MaterialCategory.SCHUETTGUT, price_min=8.0, price_max=13.0),
    MaterialItem(id="MAT-04", name="Schotter 16/32", unit=Unit.TONNE, category=MaterialCategory.SCHUETTGUT, price_min=12.0, price_max=18.0),
    MaterialItem(id="MAT-05", name="Schotter 32/56", unit=Unit.TONNE, category=MaterialCategory.SCHUETTGUT, price_min=13.0, price_max=19.0),
    # Beton (m³)
    MaterialItem(id="MAT-06", name="Beton C20/25", unit=Unit.CUBIC_METER, category=MaterialCategory.BETON, price_min=95.0, price_max=110.0),
    MaterialItem(id="MAT-07", name="Beton C25/30", unit=Unit.CUBIC_METER, category=MaterialCategory.BETON, price_min=105.0, price_max=120.0),
    MaterialItem(id="MAT-08", name="Beton C30/37", unit=Unit.CUBIC_METER, category=MaterialCategory.BETON, price_min=115.0, price_max=135.0),
    # Asphalt (t)
    MaterialItem(id="MAT-09", name="Asphalt AC 11 Deckschicht", unit=Unit.TONNE, category=MaterialCategory.ASPHALT, price_min=75.0, price_max=90.0),
    MaterialItem(id="MAT-10", name="Asphalt AC 16 Binderschicht", unit=Unit.TONNE, category=MaterialCategory.ASPHALT, price_min=70.0, price_max=85.0),
    MaterialItem(id="MAT-11", name="Asphalt AC 16 Tragschicht", unit=Unit.TONNE, category=MaterialCategory.ASPHALT, price_min=68.0, price_max=82.0),
    MaterialItem(id="MAT-12", name="Splittmastixasphalt SMA 8", unit=Unit.TONNE, category=MaterialCategory.ASPHALT, price_min=85.0, price_max=95.0),
    # Betonstahl (kg)
    MaterialItem(id="MAT-13", name="Betonstahl BSt 500 Ø8", unit=Unit.KILOGRAM, category=MaterialCategory.STAHL, price_min=0.85, price_max=1.05),
    MaterialItem(id="MAT-14", name="Betonstahl BSt 500 Ø10", unit=Unit.KILOGRAM, category=MaterialCategory.STAHL, price_min=0.85, price_max=1.05),
    MaterialItem(id="MAT-15", name="Betonstahl BSt 500 Ø12", unit=Unit.KILOGRAM, category=MaterialCategory.STAHL, price_min=0.90, price_max=1.10),
    MaterialItem(id="MAT-16", name="Betonstahlmatte Q188A", unit=Unit.KILOGRAM, category=MaterialCategory.STAHL, price_min=1.00, price_max=1.30),
    # Bordsteine (Stk)
    MaterialItem(id="MAT-17", name="Bordstein Beton grau 100x30x15", unit=Unit.PIECE, category=MaterialCategory.FERTIGTEIL, price_min=3.50, price_max=5.50),
    MaterialItem(id="MAT-18", name="Hochbordstein 100x25x15", unit=Unit.PIECE, category=MaterialCategory.FERTIGTEIL, price_min=4.00, price_max=6.00),
    MaterialItem(id="MAT-19", name="Rundbordstein 50x25x15", unit=Unit.PIECE, category=MaterialCategory.FERTIGTEIL, price_min=3.00, price_max=4.50),
    MaterialItem(id="MAT-20", name="Einfassung Rasenkantenstein 100x20x5", unit=Unit.PIECE, category=MaterialCategory.FERTIGTEIL, price_min=2.00, price_max=3.50),
]
