from flask import Flask, render_template, request, redirect, url_for
from openai import OpenAI
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import os
import json
import re
import requests
from urllib.parse import urlencode

load_dotenv()

app = Flask(__name__)

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

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


def obtenir_mapping_champs(url):
    """Récupère pour chaque champ : son entry_id, son type, et ses options si applicable."""
    reponse = requests.get(url)
    html = reponse.text

    match = re.search(r'var FB_PUBLIC_LOAD_DATA_ = (.*?);\s*</script>', html, re.DOTALL)
    if not match:
        return {}

    data = json.loads(match.group(1))
    questions = data[1][1]

    types_a_choix = {2, 3, 4}

    mapping = {}
    for question in questions:
        titre = question[1]
        type_champ = question[3]
        entries = question[4]

        if not entries or not entries[0][0]:
            continue

        entry_id = entries[0][0]
        info_champ = {
            "entry": f"entry.{entry_id}",
            "type": type_champ,
            "options": []
        }

        if type_champ in types_a_choix and len(entries[0]) > 1 and entries[0][1]:
            info_champ["options"] = [choix[0] for choix in entries[0][1] if choix[0]]

        mapping[titre] = info_champ

    return mapping


def construire_lien_prefill(url, donnees, mapping):
    """Construit l'URL du formulaire avec les réponses déjà pré-remplies."""
    params = {"usp": "pp_url"}
    for champ, valeur in donnees.items():
        if valeur and champ in mapping:
            entry_id = mapping[champ]["entry"]
            params[entry_id] = valeur

    url_propre = url.split("?")[0]
    return f"{url_propre}?{urlencode(params)}"


def extraire_infos_dynamique(texte, mapping, profil):
    profil_texte = json.dumps(profil, ensure_ascii=False)

    description_champs = []
    for titre, info in mapping.items():
        if info["options"]:
            options_texte = " / ".join(info["options"])
            description_champs.append(f'- "{titre}" : choisis EXACTEMENT une option parmi [{options_texte}]')
        else:
            description_champs.append(f'- "{titre}" : texte libre')

    description = "\n".join(description_champs)

    reponse = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": f"""Tu remplis un formulaire avec les champs suivants :
{description}

Tu disposes d'un profil mémorisé de l'utilisateur : {profil_texte}.
Utilise en priorité les informations données dans le texte de l'utilisateur.
Si une info manque dans le texte mais existe dans le profil mémorisé, utilise le profil.
Pour les champs à choix, réponds EXACTEMENT avec le texte d'une des options proposées, jamais une valeur inventée.
Si l'info n'existe nulle part ou ne correspond à aucune option valide, mets une chaîne vide ''.
Réponds UNIQUEMENT en JSON avec les titres exacts des champs comme clés."""},
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


def soumettre_formulaire_automatiquement(lien_prefill):
    """Ouvre le lien pré-rempli et clique automatiquement sur Suivant/Envoyer jusqu'à la fin."""
    os.makedirs("static", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(lien_prefill, wait_until="networkidle")
        page.wait_for_timeout(1500)

        page.screenshot(path="static/etape_0_debut.png", full_page=True)

        for i in range(15):
            bouton_suivant = page.get_by_role("button", name=re.compile("Suivant|Next", re.IGNORECASE))

            if bouton_suivant.count() > 0:
                bouton_suivant.first.click()
                page.wait_for_timeout(2000)
                page.screenshot(path=f"static/etape_{i+1}_apres_suivant.png", full_page=True)
            else:
                break

        bouton_envoyer = page.get_by_role("button", name=re.compile("Envoyer|Submit", re.IGNORECASE))
        confirmation = False

        if bouton_envoyer.count() > 0:
            bouton_envoyer.first.click()
            page.wait_for_timeout(2000)
            confirmation = True
        else:
            page.screenshot(path="static/echec_envoi.png", full_page=True)

        browser.close()
        return confirmation


@app.route("/", methods=["GET", "POST"])
def index():
    texte_precedent = None
    url_precedente = None
    lien_prefill = None
    profil = charger_profil()

    if request.method == "POST":
        texte_precedent = request.form.get("texte", "")
        url_precedente = request.form.get("url", "")

        mapping = obtenir_mapping_champs(url_precedente)

        donnees = extraire_infos_dynamique(texte_precedent, mapping, profil)
        lien_prefill = construire_lien_prefill(url_precedente, donnees, mapping)

    return render_template(
        "index.html",
        texte_precedent=texte_precedent,
        url_precedente=url_precedente,
        profil=profil,
        lien_prefill=lien_prefill
    )


@app.route("/profil", methods=["GET", "POST"])
def profil_page():
    if request.method == "POST":
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


@app.route("/soumettre", methods=["POST"])
def soumettre():
    lien = request.form.get("lien_prefill", "")
    succes = soumettre_formulaire_automatiquement(lien) if lien else False
    return render_template("confirmation.html", succes=succes)


@app.route("/debug")
def debug():
    fichiers = sorted(os.listdir("static")) if os.path.exists("static") else []
    html = "<h1>Captures de debug</h1>"
    for f in fichiers:
        html += f"<h3>{f}</h3><img src='/static/{f}' style='max-width:600px; border:1px solid #ccc; margin-bottom:20px;'><br>"
    return html


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)