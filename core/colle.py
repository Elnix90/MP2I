from dataclasses import dataclass


@dataclass
class Colle:
    colleur_name: str
    matiere: str
    jour: str
    creneau: int
    salle: str
    is_future: bool

    def __str__(self) -> str:
        prefix = ""
        suffix = ""

        # Skiletrough the line when the colle is already done
        if not self.is_future:
            prefix = "~~"
            suffix = "~~"

        if self.colleur_name == "Gaudillat":
            suffix = " (tu es foutu)" + suffix

        return f"{prefix} **{self.matiere}**, {self.jour} de {self.creneau}h à {self.creneau + 1}h avec ***{self.colleur_name}*** en salle **{self.salle}**. {suffix}"


@dataclass
class ColleResult:
    colles: list[Colle]
    fetched_week: int
    current_week: int

    def week_str(self) -> str:
        diff = self.fetched_week - self.current_week

        match diff:
            case 0:
                return "***__Cette semaine__***"
            case 1:
                return "***__La semaine prochaine__***"
            case _:
                return f"***__La semaine n°{self.fetched_week}__***"
