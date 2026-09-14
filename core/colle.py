class Colle:
    def __init__(self, colleur_name: str, matiere: str, jour: str, creneau: str, salle: str) -> None:
        self.colleur_name = colleur_name
        self.matiere = matiere
        self.jour = jour
        self.creneau = creneau
        self.salle = salle

    def __str__(self) -> str:

        if self.colleur_name == "Gaudillat":
            end_msg = " (tu es foutu)"
        else:
            end_msg = ""
   
        return f"Colle de {self.matiere}, {self.jour} à {self.creneau} par {self.colleur_name} en sall {self.salle}{end_msg}"