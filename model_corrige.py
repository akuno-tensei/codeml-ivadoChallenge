"""
EquiAlgo : modele corrige.

Etapes :
  1. On modelise la decision du comite avec une regression logistique.
  2. On separe ce qui releve du merite (cote R, heures travaillees)
     et ce qui releve du biais (region, revenu familial).
  3. On retire le biais petit a petit (parametre lambda de 0 a 1)
     et on trace le front de Pareto equite / fidelite au comite.
  4. On accorde la bourse aux 1600 meilleurs candidats (40 %) selon
     le score de merite, sans region ni proxy de region.

Usage : python model_corrige.py
Sorties : predictions.csv, figures/pareto_front.png, figures/taux_par_region.png
"""
import os
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from fairlearn.postprocessing import ThresholdOptimizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

warnings.filterwarnings("ignore")
os.makedirs("figures", exist_ok=True)

ELOIGNEES = ["Bas-Saint-Laurent", "Cote-Nord", "Gaspesie-Iles-de-la-Madeleine"]
N_BOURSES = 1600          # 40 % de 4000, au milieu de la plage permise (36 % a 44 %)
SEED = 42


# ---------------------------------------------------------------- donnees
def preparer(df):
    df = df.copy()
    df["eloignee"] = df["region_administrative"].isin(ELOIGNEES).astype(int)
    df["log_revenu"] = np.log(df["revenu_familial_estime"])
    return df


hist = preparer(pd.read_csv("data/donnees_demandes.csv"))
cand = preparer(pd.read_csv("data/candidats_evaluation.csv"))
train, test = train_test_split(hist, test_size=0.3, random_state=SEED,
                               stratify=hist["decision_octroi"])

# ---------------------------------------------------------------- 1. le comite
FORMULE = ("decision_octroi ~ cote_r_equivalent + heures_travail_semaine"
           " + log_revenu + eloignee")
comite = smf.logit(FORMULE, data=hist).fit(disp=0)
b = comite.params
print(comite.summary().tables[1])

# On exprime chaque effet en "points de cote R" pour le rendre lisible.
POIDS_HEURES = b["heures_travail_semaine"] / b["cote_r_equivalent"]
PENALITE_REGION = -b["eloignee"] / b["cote_r_equivalent"]
PRIME_REVENU = b["log_revenu"] / b["cote_r_equivalent"]
print(f"\nUne heure de travail par semaine vaut {POIDS_HEURES:.3f} point de cote R")
print(f"Habiter en region eloignee coute {PENALITE_REGION:.2f} point de cote R")
print(f"Doubler le revenu familial rapporte {PRIME_REVENU * np.log(2):.2f} point de cote R")


# ---------------------------------------------------------------- 2. scores
def score(df, lam):
    """Score du comite dont on retire une part lam du biais.

    lam = 0 : on reproduit le comite (region et revenu comptent).
    lam = 1 : merite seul, cote R + heures travaillees.
    """
    merite = df["cote_r_equivalent"] + POIDS_HEURES * df["heures_travail_semaine"]
    biais = (PRIME_REVENU * (df["log_revenu"] - hist["log_revenu"].mean())
             - PENALITE_REGION * df["eloignee"])
    return merite + (1 - lam) * biais


def top(s, part=0.40):
    s = np.asarray(s, dtype=float)
    return (s >= np.quantile(s, 1 - part)).astype(int)


def mesures(pred, df, merite_ref):
    """Ecart de parite, ecart d'egalite des chances et accord avec le comite."""
    g = df["eloignee"].values
    pred = np.asarray(pred)
    tpr = [pred[(merite_ref == 1) & (g == k)].mean() for k in (0, 1)]
    return {
        "taux_octroi": pred.mean(),
        "ecart_parite": pred[g == 0].mean() - pred[g == 1].mean(),
        "ecart_egalite_chances": tpr[0] - tpr[1],
        "accord_comite": (pred == df["decision_octroi"].values).mean(),
    }


# Reference de merite sur l'historique (sert a mesurer l'egalite des chances).
merite_test = top(score(test, 1.0))

# ---------------------------------------------------------------- 3. front de Pareto
lignes = []
for lam in np.round(np.linspace(0, 1, 11), 1):
    m = mesures(top(score(test, lam)), test, merite_test)
    lignes.append({"methode": f"lambda={lam}", "lam": lam, **m})

# Points de comparaison : le modele en production et deux corrections fairlearn.
CAT = ["programme_etudes", "region_administrative", "code_postal_3"]
COLS = ["cote_r_equivalent", "revenu_familial_estime", "heures_travail_semaine",
        "distance_domicile_campus_km", "premiere_generation_universitaire"] + CAT


def encoder(a, c):
    xa = pd.get_dummies(a[COLS], columns=CAT)
    xc = pd.get_dummies(c[COLS], columns=CAT).reindex(columns=xa.columns, fill_value=0)
    return xa, xc


Xtr, Xte = encoder(train, test)
rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=20, random_state=SEED)
rf.fit(Xtr, train["decision_octroi"])
lignes.append({"methode": "production (foret aleatoire)", "lam": np.nan,
               **mesures(rf.predict(Xte), test, merite_test)})
for contrainte in ["demographic_parity", "true_positive_rate_parity"]:
    to = ThresholdOptimizer(
        estimator=RandomForestClassifier(n_estimators=300, min_samples_leaf=20, random_state=SEED),
        constraints=contrainte, predict_method="predict_proba")
    to.fit(Xtr, train["decision_octroi"], sensitive_features=train["eloignee"])
    p = to.predict(Xte, sensitive_features=test["eloignee"], random_state=SEED)
    lignes.append({"methode": f"fairlearn {contrainte}", "lam": np.nan,
                   **mesures(p, test, merite_test)})

front = pd.DataFrame(lignes)
front.to_csv("experiences/front_pareto.csv", index=False)
print("\n", front.round(3).to_string(index=False))

fig, ax = plt.subplots(figsize=(7, 5))
f = front.dropna(subset=["lam"])
ax.plot(f["ecart_egalite_chances"], f["accord_comite"], "o-", color="#2b6cb0", label="retrait progressif du biais")
for _, r in f.iterrows():
    ax.annotate(f"λ={r.lam:.1f}", (r.ecart_egalite_chances, r.accord_comite),
                fontsize=8, xytext=(5, 3), textcoords="offset points")
autres = front[front["lam"].isna()]
for (_, r), mk in zip(autres.iterrows(), ["s", "^", "v"]):
    ax.scatter(r.ecart_egalite_chances, r.accord_comite, marker=mk, s=70, label=r.methode)
ax.axvline(0, color="grey", lw=0.8, ls=":")
ax.set_xlabel("Ecart d'egalite des chances (centres moins regions eloignees)")
ax.set_ylabel("Accord avec les decisions du comite")
ax.set_title("Front de Pareto : equite contre fidelite au comite")
ax.legend(fontsize=8, loc="lower right")
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig("figures/pareto_front.png", dpi=150)

# ---------------------------------------------------------------- 4. predictions
s_final = score(cand, 1.0).values
ordre = np.lexsort((cand["id_candidat"].values, -cand["cote_r_equivalent"].values, -s_final))
pred = np.zeros(len(cand), dtype=int)
pred[ordre[:N_BOURSES]] = 1

sortie = pd.DataFrame({"id_candidat": cand["id_candidat"], "decision_octroi": pred})
sortie.to_csv("predictions.csv", index=False)

taux = pred.mean()
assert 0.36 <= taux <= 0.44, "Hors budget"
print(f"\npredictions.csv ecrit : {len(sortie)} lignes, taux d'octroi {taux:.1%}")
par_region = (sortie.assign(region=cand["region_administrative"])
              .groupby("region")["decision_octroi"].mean())
print(par_region.round(3))

# Comparaison avec le modele en production sur les memes candidats.
Xh, Xc = encoder(hist, cand)
prod = RandomForestClassifier(n_estimators=300, min_samples_leaf=20, random_state=SEED)
prod.fit(Xh, hist["decision_octroi"])
avant = pd.Series(prod.predict(Xc)).groupby(cand["region_administrative"]).mean()
comp = pd.DataFrame({"modele en production": avant, "modele corrige": par_region})
ax = comp.plot.bar(figsize=(7, 4), color=["#c05621", "#2b6cb0"], rot=20)
ax.set_ylabel("Taux d'octroi")
ax.set_title("Taux d'octroi par region, 4000 candidats a evaluer")
ax.set_ylim(0, 0.6)
ax.legend(loc="upper center", ncol=2)
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig("figures/taux_par_region.png", dpi=150)
