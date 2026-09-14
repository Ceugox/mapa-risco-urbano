import re
import unicodedata

TIPOS = r"^(AV|AVENIDA|R|RUA|PCA|PC|PTE|VD|EST|ROD|MARG|MARGINAL|CV|TUN|TRV|AL|LGO|ACS|COMPL)\b\.?\s*"
TITULOS = r"^(CEL|CAP|TEN|SGT|GEN|MAL|BRIG|DR|DRA|PROF|PROFA|PE|SEN|DEP|VER|GOV|PRES|MIN|ENG|JORN|SARG|VIS|CDE|CDSSA|MAJ)\b\.?\s*"


def normaliza(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.upper())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\(.*?\)", " ", texto)
    texto = re.split(r"[-–]", texto)[0]
    texto = re.sub(r"[.,]", " ", texto).strip()
    texto = re.sub(TIPOS, "", texto).strip()
    texto = re.sub(TITULOS, "", texto).strip()
    return re.sub(r"\s+", " ", texto).strip()
