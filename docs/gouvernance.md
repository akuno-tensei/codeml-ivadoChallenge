# Gouvernance et plan de suivi en production

Corriger le modèle une fois ne suffit pas. Les candidats changent, les règles changent, et un biais peut revenir sans que personne ne le voie. Voici comment on garderait le modèle juste une fois en production.

## 1. Les principes

- **Le modèle aide, il ne décide pas seul.** Il propose une liste. Un comité humain la valide.
- **Le mérite se définit par écrit.** Aujourd'hui : cote R plus effort de travail (heures travaillées). Toute nouvelle variable doit être justifiée et approuvée avant d'entrer dans le score.
- **Jamais de région ni de proxy de région dans le score.** Code postal, distance et revenu familial sont exclus. On les garde seulement pour l'audit.
- **Chaque candidat peut comprendre sa décision.** Le score se lit en une ligne : cote R + 0,145 × heures travaillées par semaine.

## 2. Ce qu'on mesure à chaque cohorte

| Indicateur | Comment | Seuil d'alerte |
|---|---|---|
| Taux d'octroi global | part des candidats retenus | hors de 36 % à 44 % |
| Taux d'octroi par région (5 régions) | part retenue dans chaque région | écart de plus de 8 points avec la moyenne |
| Égalité des chances | parmi les dossiers au-dessus du seuil de mérite, part retenue par région | écart de plus de 0,05 entre centres et régions |
| Cote R moyenne par région | suivi de la distribution | variation de plus de 0,5 point d'une année à l'autre |
| Stabilité du score | comparaison avec l'année précédente (PSI) | PSI > 0,2 |
| Cas limites | dossiers à moins de 0,3 point du seuil | toujours revus par un humain |

Les petites régions (Côte-Nord, environ 500 candidats) bougent de quelques points par simple hasard. On affiche donc un intervalle de confiance à côté de chaque taux, et on regarde la tendance sur deux ou trois cohortes avant de conclure.

## 3. Qui fait quoi

- **Équipe données** : produit le tableau de bord à chaque cohorte et lance les alertes.
- **Comité d'équité** (3 à 5 personnes, dont une personne externe à l'institution et une personne qui connaît bien les régions) : lit le tableau de bord et décide des corrections.
- **Comité d'octroi** : valide la liste finale et revoit les cas limites.

## 4. Quand une alerte sonne

1. On vérifie d'abord les données (erreur de saisie, nouveau formulaire, nouvelle région).
2. On regarde si l'écart vient du mérite réel (cote R plus basse cette année) ou du modèle.
3. Si c'est le modèle : on revient à la version précédente, on corrige, on reteste sur l'historique.
4. On note la décision dans le journal des versions.

## 5. Audit annuel

- Un audit complet chaque année, comme `audit_rapport.ipynb`, refait sur les nouvelles données.
- On compare les boursiers à leur réussite réelle (diplôme, moyenne à l'université). Si les boursiers des régions réussissent aussi bien que les autres, la définition du mérite tient la route.
- On publie un résumé public : taux par région, écarts, changements apportés.

## 6. Droit de recours

- Chaque candidat refusé reçoit son score et le seuil de l'année.
- Il peut demander une revue humaine, par exemple pour une situation que le score ne voit pas (maladie, proche aidant, etc.).
- Les recours acceptés sont comptés et analysés. S'ils viennent surtout d'une région ou d'un groupe, c'est un signal d'alerte.

## 7. Limites connues

- La définition du mérite est un choix de valeurs. Elle doit être revue avec des personnes concernées, pas seulement des techniciens.
- La cote R elle-même peut porter un biais (écoles moins financées, moins de cours offerts en région). Ce modèle ne le corrige pas. Ce serait la prochaine étape.
- Les données du défi sont synthétiques. Avant un vrai déploiement, tout doit être revalidé sur des données réelles.
