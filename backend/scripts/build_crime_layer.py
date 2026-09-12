import json
import sys
from collections import defaultdict
from pathlib import Path

import h3
import openpyxl
from shapely.geometry import Polygon, mapping

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path("/home/ubuntu/risco-urbano-probes/sp2026.xlsx")
OUTPUT = ROOT / "backend" / "data" / "crime_h3.json"


def coordenada_valida(lat, lon):
    try:
        lat_f, lon_f = float(str(lat).replace(",", ".")), float(str(lon).replace(",", "."))
    except (TypeError, ValueError):
        return False
    return lat_f != 0 and lon_f != 0 and -34 < lat_f < 6 and -74 < lon_f < -34


def group(value):
    value = str(value or "").upper()
    if value.startswith("FURTO"):
        return "furto"
    if value.startswith("ROUBO"):
        return "roubo"
    if "VEÍCULO" in value or "VEICULO" in value:
        return "veiculo"
    if value.startswith(("LESÃO", "LESAO")):
        return "lesao"
    return "outros"


def main():
    cells = defaultdict(lambda: {"total": 0, "furto": 0, "roubo": 0, "veiculo": 0, "lesao": 0, "outros": 0})
    for sheet in ("JAN-JUN_2026", "JUL-DEZ_2026"):
        workbook = openpyxl.load_workbook(SOURCE, read_only=True)
        rows = workbook[sheet].iter_rows(values_only=True)
        headers = {name: i for i, name in enumerate(next(rows))}
        for row in rows:
            municipality = str(row[headers["NOME_MUNICIPIO"]] or "").strip().upper()
            if municipality != "S.PAULO" or "VEDAÇÃO" in str(row[headers["LOGRADOURO"]] or "").upper():
                continue
            lat, lon = row[headers["LATITUDE"]], row[headers["LONGITUDE"]]
            if not coordenada_valida(lat, lon):
                continue
            cell = h3.latlng_to_cell(float(lat), float(lon), 8)
            bucket = cells[cell]
            bucket["total"] += 1
            bucket[group(row[headers["NATUREZA_APURADA"]])] += 1
        workbook.close()
    features = []
    for cell, properties in cells.items():
        if properties["total"] < 5:
            continue
        boundary = h3.cell_to_boundary(cell)
        polygon = Polygon([(lon, lat) for lat, lon in boundary] + [(boundary[0][1], boundary[0][0])])
        features.append({"type": "Feature", "geometry": mapping(polygon), "properties": {"h3": cell, **properties, "periodo": "2026-01..2026-07"}})
    OUTPUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False))
    print(f"{len(features)} células gravadas em {OUTPUT}")


if __name__ == "__main__":
    sys.exit(main())
