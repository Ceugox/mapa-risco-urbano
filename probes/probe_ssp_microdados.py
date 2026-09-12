"""Mede a base de microdados criminais da SSP-SP (SPDadosCriminais).

Perguntas que este script responde:
  - qual a defasagem real (data de ocorrencia mais recente)?
  - quantos registros tem coordenada utilizavel?
  - quais naturezas dominam e quais tem endereco suprimido por lei?
  - da para agregar espacialmente no municipio de Sao Paulo?
"""

import collections
import json
import sys
import time
from datetime import datetime, timezone

import openpyxl

ARQUIVO = "sp2026.xlsx"
ABAS = ["JAN-JUN_2026", "JUL-DEZ_2026"]


def coordenada_valida(lat, lon) -> bool:
    """A base traz '-', 0 ou vazio quando o endereco foi suprimido ou nao geocodificado."""
    try:
        lat_f, lon_f = float(str(lat).replace(",", ".")), float(str(lon).replace(",", "."))
    except (TypeError, ValueError):
        return False
    return lat_f != 0 and lon_f != 0 and -34 < lat_f < 6 and -74 < lon_f < -34


def analisa() -> dict:
    started = time.monotonic()
    wb = openpyxl.load_workbook(ARQUIVO, read_only=True)

    total = 0
    com_coord = 0
    sp_capital = 0
    sp_capital_com_coord = 0
    logradouro_suprimido = 0
    naturezas: collections.Counter = collections.Counter()
    por_mes: collections.Counter = collections.Counter()
    data_max = None

    for aba in ABAS:
        ws = wb[aba]
        it = ws.iter_rows(values_only=True)
        header = list(next(it))
        idx = {nome: i for i, nome in enumerate(header)}

        for row in it:
            if row is None or row[idx["ANO_BO"]] is None:
                continue
            total += 1

            tem_coord = coordenada_valida(row[idx["LATITUDE"]], row[idx["LONGITUDE"]])
            if tem_coord:
                com_coord += 1

            if str(row[idx["NOME_MUNICIPIO"]]).strip().upper() in {"S.PAULO", "SAO PAULO", "SÃO PAULO"}:
                sp_capital += 1
                if tem_coord:
                    sp_capital_com_coord += 1

            if "VEDAÇÃO" in str(row[idx["LOGRADOURO"]] or "").upper():
                logradouro_suprimido += 1

            naturezas[row[idx["NATUREZA_APURADA"]]] += 1

            ocorrencia = row[idx["DATA_OCORRENCIA_BO"]]
            if isinstance(ocorrencia, datetime):
                por_mes[ocorrencia.strftime("%Y-%m")] += 1
                if data_max is None or ocorrencia > data_max:
                    data_max = ocorrencia

    hoje = datetime.now()
    return {
        "fonte": "SSP-SP / SPDadosCriminais 2026",
        "coletado_em": datetime.now(timezone.utc).isoformat(),
        "tempo_processamento_s": round(time.monotonic() - started, 1),
        "registros": total,
        "com_coordenada_valida": com_coord,
        "pct_com_coordenada": round(100 * com_coord / total, 1) if total else 0,
        "municipio_sao_paulo": sp_capital,
        "municipio_sao_paulo_com_coordenada": sp_capital_com_coord,
        "logradouro_suprimido_por_lei": logradouro_suprimido,
        "ocorrencia_mais_recente": data_max.date().isoformat() if data_max else None,
        "defasagem_dias": (hoje - data_max).days if data_max else None,
        "registros_por_mes": dict(sorted(por_mes.items())),
        "top_naturezas": naturezas.most_common(12),
    }


def main() -> int:
    relatorio = analisa()
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    with open("saida_ssp.json", "w", encoding="utf-8") as fh:
        json.dump(relatorio, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
