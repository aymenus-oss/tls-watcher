"""
tls_watcher_login.py — Se connecte à TLScontact avec email + mot de passe
à chaque exécution (pas besoin de renouveler une session manuellement),
vérifie la disponibilité, et alerte via Telegram.
"""

import os
import sys
from datetime import datetime

import requests
from playwright.sync_api import sync_playwright

APPOINTMENT_URL = "https://visas-fr.tlscontact.com/workflow/appointment-booking/tnTUN2fr/28524102"

NO_SLOT_TEXTS = [
    "aucun rendez-vous disponible",
    "aucun rendez vous disponible",
    "no appointment available",
    "no slots available",
]

TLS_EMAIL = os.environ.get("TLS_EMAIL", "")
TLS_PASSWORD = os.environ.get("TLS_PASSWORD", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def send_telegram(message: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log("[!] TELEGRAM_TOKEN / TELEGRAM_CHAT_ID manquants.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=15)
        if r.status_code != 200:
            log(f"[!] Erreur Telegram: {r.status_code} {r.text}")
    except Exception as e:
        log(f"[!] Impossible d'envoyer l'alerte Telegram: {e}")


def main():
    if not TLS_EMAIL or not TLS_PASSWORD:
        log("[!] TLS_EMAIL / TLS_PASSWORD manquants.")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
        )
        page = context.new_page()

        try:
            log("Chargement de la page de rendez-vous (redirige vers le login si besoin)...")
            page.goto(APPOINTMENT_URL, timeout=45000)
            page.wait_for_timeout(3000)

            if page.locator("#username").count() > 0 or page.locator("input[type='email']").count() > 0:
                log("Page de connexion détectée, remplissage du formulaire...")

                email_field = page.locator("#username")
                if email_field.count() == 0:
                    email_field = page.locator("input[type='email']")
                email_field.first.fill(TLS_EMAIL)

                password_field = page.locator("#password")
                if password_field.count() == 0:
                    password_field = page.locator("input[type='password']")
                password_field.first.fill(TLS_PASSWORD)

                submit_button = page.locator("#kc-login")
                if submit_button.count() == 0:
                    submit_button = page.locator("button[type='submit']")
                submit_button.first.click()

                page.wait_for_timeout(5000)

            content = page.content().lower()

            if "captcha" in content or "cloudflare" in content or "attention required" in content:
                log("Blocage probable par une protection anti-robot (Cloudflare/captcha).")
                send_telegram(
                    "⚠️ Le script s'est fait bloquer par la protection anti-robot du site. "
                    "Cette méthode automatique ne fonctionne pas de manière fiable pour ce site — "
                    "il faudra repasser par une vérification manuelle ou trouver une autre approche."
                )
                return

            if any(t in content for t in ["identifiants incorrects", "invalid credentials", "mot de passe incorrect"]):
                log("Email/mot de passe refusés par le site.")
                send_telegram("⚠️ Connexion refusée : vérifie TLS_EMAIL et TLS_PASSWORD dans les secrets GitHub.")
                return

            no_slot_found = any(t in content for t in NO_SLOT_TEXTS)

            if no_slot_found:
                log("Toujours aucun créneau.")
            else:
                log("!!! Un créneau semble disponible !")
                send_telegram(
                    "🚨 Un créneau semble disponible sur TLScontact Tunis !\n"
                    f"{APPOINTMENT_URL}\n"
                    "Vérifie et réserve vite."
                )

        except Exception as e:
            log(f"Erreur pendant la vérification: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
