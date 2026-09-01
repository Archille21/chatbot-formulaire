from playwright.sync_api import sync_playwright
import os

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    # Chemin absolu vers notre fichier local
    chemin = "file://" + os.path.abspath("formulaire.html")
    page.goto(chemin)

    # On remplit les champs automatiquement
    page.fill("#nom", "Jean Dupont")
    page.fill("#email", "jean.dupont@email.com")
    page.fill("#message", "Ceci est un message rempli automatiquement !")

    # On attend 5 secondes pour voir le résultat
    page.wait_for_timeout(5000)

    browser.close()