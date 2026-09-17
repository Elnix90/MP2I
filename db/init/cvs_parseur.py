'''
csv parseur
'''

MATIERES = {"MATHS": 0,"ANGLAIS": 1,"PHYSIQUE": 2, "INFO": 3}
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

def csv_parse(name:str) -> list[tuple[int,int,int,int,str,dict]]:
    with open(name) as f:
        l_lignes = f.readlines()
    for i in range(4):
        l_lignes.pop(0)
    l_lignes.pop(-1)
    l_lignes.pop(-1)
    n = len(l_lignes)
    for i in range(n):
        l_lignes[i] = l_lignes[i].replace(' ','')
        l_lignes[i] = l_lignes[i].replace('\n','')
 
    l_matiere = iter([MATIERES[st.split(',')[1]] for st in l_lignes if st[1] != ','])
    
    ROWS = [[l_lignes[i].split(',')[j] for j in range(1,5)]+[{k+1: int(l_lignes[i].split(',')[5:len(l_lignes[i].split(','))][k]) for k in range(len(l_lignes[i].split(',')[5:len(l_lignes[i].split(','))])) if l_lignes[i].split(',')[5:len(l_lignes[i].split(','))][k] != ''}] for i in range(n) if l_lignes[i] != ',,,,,,,,,,,,,,,,,,,']
    
    n1 = len(ROWS)
    for i in range(n1):
        if ROWS[i][0] != '':
            matiere = next(l_matiere)
        ROWS[i][0] = matiere
        ROWS[i][1] = COLLEURS[ROWS[i][1]]
        ROWS[i].insert(3,int(ROWS[i][2][-5:-3]))
        ROWS[i][2] = JOURS[ROWS[i][2][0:-5]]
        ROWS[i] = tuple(ROWS[i])
    
    return ROWS
    