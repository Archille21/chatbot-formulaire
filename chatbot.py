from openai import OpenAI
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import os
import json

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

def extraire_infos(texte):
    """Demande à DeepSeek d'extraire nom, email et message du texte."""
    reponse = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "Tu extrais des informations d'un texte et tu réponds UNIQUEMENT en JSON avec les clés: nom, email, message. Rien d'autre."},
            {"role": "user", "content": texte}
        ]
    )
    return json.loads(reponse.choices[0].message.content)

def remplir_formulaire(donnees):
    """Remplit automatiquement un Google Form avec les données extraites."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        url_formulaire = "https://docs.google.com/forms/d/e/1FAIpQLScUGH8aHG2E6tFym6h5acaKMsEXTXDfSlYV4Y6mA3OwXXCI3g/viewform"
        page.goto(url_formulaire)

        # On cible chaque champ par son label (le texte de la question)
        page.get_by_role("textbox", name="Nom").fill(donnees["nom"])
        page.get_by_role("textbox", name="Email").fill(donnees["email"])
        page.get_by_role("textbox", name="Message").fill(donnees["message"])

        page.wait_for_timeout(8000)  # temps pour vérifier avant fermeture
        browser.close()

# --- Programme principal ---
print("🤖 Bonjour ! Décris-moi tes infos (nom, email, message) en une phrase :")
texte_utilisateur = input("> ")

print("\n🔍 Analyse en cours...")
donnees = extraire_infos(texte_utilisateur)
print(f"✅ J'ai compris : {donnees}")

print("\n📝 Remplissage du formulaire...")
remplir_formulaire(donnees)
print("✅ Terminé !")