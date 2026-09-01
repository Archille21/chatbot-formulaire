from openai import OpenAI
from dotenv import load_dotenv
import os
import json

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

texte_utilisateur = "Je m'appelle Marie Curie, mon email est marie@labo.fr, et mon message c'est que je veux plus d'infos sur le poste"

reponse = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "Tu extrais des informations d'un texte et tu réponds UNIQUEMENT en JSON avec les clés: nom, email, message. Rien d'autre, pas de texte avant ou après."},
        {"role": "user", "content": texte_utilisateur}
    ]
)

resultat = reponse.choices[0].message.content
print(resultat)

# On transforme le texte JSON en vraie donnée Python
donnees = json.loads(resultat)
print(donnees["nom"])
print(donnees["email"])
print(donnees["message"])