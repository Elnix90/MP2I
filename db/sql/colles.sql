SELECT c.nom AS colleur_name,
       m.nom AS matiere,
       p.jour_id,
       p.creneau_start,
       p.salle
FROM planning p
JOIN colleurs c ON c.id = p.colleur_id
JOIN matieres m ON m.id = p.matiere_id
WHERE p.groupe = ?
  AND p.semaine = ?