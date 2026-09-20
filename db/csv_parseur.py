"""csv parseur"""

from typing import Any

from db.init.rows import ROWS

MATIERES = {"MATHS": 0, "ANGLAIS": 1, "PHYSIQUE": 2, "INFO": 3}
COLLEURS = {
    "Vinsu": 0,
    "Chabauty": 1,
    "Chevassus": 2,
    "Lefevre": 3,
    "David": 4,
    "Vincent": 5,
    "Nicolas": 6,
    "Ratte": 7,
    "Mensah": 8,
    "Ulliac": 9,
    "Rodriguez": 10,
    "Gaudillat": 11,
    "Funes": 12,
    "Jeanneret": 13,
    "Torterotot": 14,
    "Pesenti": 15,
}
JOURS = {
    "Lundi": 0,
    "Mardi": 1,
    "Mercredi": 2,
    "Jeudi": 3,
    "Vendredi": 4,
    "Samedi": 5,
    "Dimanche": 6,
}


def csv_parse(name: str) -> list[tuple[int, int, int, int, str, dict]]:
    with open(name) as f:
        l_lignes = f.readlines()

    for i in range(4):
        l_lignes.pop(0)

    l_lignes.pop(-1)
    l_lignes.pop(-1)

    n = len(l_lignes)

    for i in range(n):
        l_lignes[i] = l_lignes[i].replace(" ", "")
        l_lignes[i] = l_lignes[i].replace("\n", "")

    l_matiere = iter([MATIERES[st.split(",")[1]] for st in l_lignes if st[1] != ","])

    matiere = 0
    rows: list[Any] = [
        [l_lignes[i].split(",")[j] for j in range(1, 5)]
        + [
            {
                k + 1: int(l_lignes[i].split(",")[5 : len(l_lignes[i].split(","))][k])
                for k in range(
                    len(l_lignes[i].split(",")[5 : len(l_lignes[i].split(","))]),
                )
                if l_lignes[i].split(",")[5 : len(l_lignes[i].split(","))][k] != ""
            },
        ]
        for i in range(n)
        if l_lignes[i] != ",,,,,,,,,,,,,,,,,,,"
    ]

    n1 = len(rows)
    for i in range(n1):
        if rows[i][0] != "":
            matiere = next(l_matiere)
        rows[i][0] = matiere
        rows[i][1] = COLLEURS[rows[i][1]]
        rows[i].insert(3, int(rows[i][2][-5:-3]))
        rows[i][2] = JOURS[rows[i][2][0:-5]]
        rows[i] = tuple(rows[i])

    return rows  # type: ignore[return-value]


if __name__ == "__main__":
    rows = csv_parse("db/init/Colloscope MP2I S1.csv")
    print(rows)
    print(rows == ROWS)
