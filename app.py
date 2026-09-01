from flask import Flask, render_template, request
from openai import OpenAI
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import os
import json
import re
from flask import Flask, render_template, request, redirect, url_for

FICHIER_PROFIL = "profil.json"

def charger_profil():
    """Charge le profil mémorisé, ou un profil vide s'il n'existe pas encore."""
    if os.path.exists(FICHIER_PROFIL):
        with open(FICHIER_PROFIL, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def sauvegarder_profil(donnees):
    """Sauvegarde le profil mis à jour."""
    with open(FICHIER_PROFIL, "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=2)
load_dotenv()

app = Flask(__name__)

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


def detecter_champs(page):
    """Scanne la page et retourne la liste des labels des champs texte trouvés."""
    snapshot = page.locator("body").aria_snapshot()
    champs = re.findall(r'textbox\s+"([^"]+)"', snapshot)
    return champs


def extraire_infos_dynamique(texte, champs, profil):
    liste_champs = ", ".join(champs)
    profil_texte = json.dumps(profil, ensure_ascii=False)
    reponse = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": f"""Tu remplis un formulaire qui a EXACTEMENT ces champs : {liste_champs}.
Tu disposes d'un profil mémorisé de l'utilisateur : {profil_texte}.
Utilise en priorité les informations données dans le texte de l'utilisateur.
Si une info manque dans le texte mais existe dans le profil mémorisé, utilise le profil.
Si l'info n'existe ni dans le texte ni dans le profil, mets une chaîne vide ''.
Réponds UNIQUEMENT en JSON avec les champs exacts comme clés."""},
            {"role": "user", "content": texte}
        ]
    )
    return json.loads(reponse.choices[0].message.content)


def remplir_formulaire_dynamique(url, donnees):
    resultats_remplissage = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)

        for champ, valeur in donnees.items():
            if valeur:
                try:
                    page.get_by_role("textbox", name=champ).first.fill(valeur)
                    resultats_remplissage[champ] = "✅ rempli"
                except Exception:
                    resultats_remplissage[champ] = "⚠️ champ non trouvé"

        page.wait_for_timeout(3000)
        browser.close()
    return resultats_remplissage
@app.route("/", methods=["GET", "POST"])
def index():
    resultat = None
    texte_precedent = None
    url_precedente = None
    profil = charger_profil()

    if request.method == "POST":
        texte_precedent = request.form.get("texte", "")
        url_precedente = request.form.get("url","")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url_precedente)
            champs = detecter_champs(page)
            browser.close()

        donnees = extraire_infos_dynamique(texte_precedent, champs, profil)
        resultat = remplir_formulaire_dynamique(url_precedente, donnees)

    return render_template(
        "index.html",
        resultat=resultat,
        texte_precedent=texte_precedent,
        url_precedente=url_precedente,
        profil=profil
    )


@app.route("/profil", methods=["GET", "POST"])
def profil_page():
    if request.method == "POST":
        # On récupère toutes les paires clé/valeur envoyées par le formulaire
        nouveau_profil = {}
        cles = request.form.getlist("cle")
        valeurs = request.form.getlist("valeur")
        for cle, valeur in zip(cles, valeurs):
            if cle.strip():
                nouveau_profil[cle.strip()] = valeur.strip()
        sauvegarder_profil(nouveau_profil)
        return redirect(url_for("profil_page"))

    profil = charger_profil()
    return render_template("profil.html", profil=profil)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
