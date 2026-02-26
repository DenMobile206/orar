# Orar – Telegram Attendance Bot

Bot Telegram pentru evidența prezenței la cursuri universitare.  
Toate mesajele UI sunt în **română**. Accesul este restricționat printr-o listă albă (`whitelist`).

---

## Structură proiect

```
bot/
  main.py              # Punct de intrare
  config.yaml          # Configurare (token, orar, semestru)
  config_loader.py     # Citire YAML
  storage.py           # Layer SQLite (aiosqlite)
  schedule.py          # Calcul tip săptămână / calendar didactic
  keyboards.py         # Fabrici de taste + CallbackData
  export_excel.py      # Generare raport .xlsx
  handlers/
    start.py           # /start
    today.py           # "Astăzi" + "Alege zi"
    mark.py            # FSM marcare prezență
    edit.py            # FSM editare prezență
    stats.py           # Statistici
    export.py          # Export Excel
    settings.py        # Setări utilizator
    admin_schedule.py  # Admin: gestionare orar
requirements.txt
README.md
```

---

## Instalare și rulare

### 1. Cerințe sistem
- Python 3.11+

### 2. Instalare dependențe

```bash
pip install -r requirements.txt
```

### 3. Configurare

Editează `bot/config.yaml`:

```yaml
telegram:
  token: "TOKEN_BOT_TĂU"   # obținut de la @BotFather

whitelist:
  - 123456789   # înlocuiește cu ID-urile Telegram reale
```

> ID-ul tău Telegram îl poți afla scriind `/start` la [@userinfobot](https://t.me/userinfobot).

### 4. Rulare

```bash
python bot/main.py
# sau
python -m bot.main
```

---

## Funcționalități

| Buton | Descriere |
|-------|-----------|
| **Astăzi** | Afișează orele din ziua curentă cu statusul prezenței |
| **Alege zi** | Selectează o zi din ultimele 7 zile pentru vizualizare |
| **Marchează prezența** | FSM pas-cu-pas: zi → săptămână → grupă → ședință → ✔/✖ |
| **Editează** | Modifică o prezență deja înregistrată |
| **Statistici** | Procente prezență per disciplină, cu filtru C/L/P |
| **Export Excel** | Trimite fișier `.xlsx` cu sumar + log complet |
| **Setări** | Schimbă grupa implicită (A/B) și tipul de săptămână |
| **Admin: Orare** | Vizualizare, adăugare, editare, ștergere ședințe; backup JSON |

---

## Calendar didactic

- **Semestrul II 2025-2026**: 23 feb – 9 apr + 20 apr – 5 iun (14 săptămâni)
- **Vacanță**: 10–19 apr 2026
- Săptămâna 1 (23 feb) = **IMPARĂ**, alternează în continuare
- Săptămâna 8 (20 apr) = **PARĂ** (continuă alternarea după vacanță)

---

## Baza de date

SQLite (`attendance.db`) generat automat la prima rulare:

- `schedule_sessions` – ședințe orar (disciplină, tip, sală, oră, profesor)
- `attendance` – înregistrări prezență per utilizator/ședință/dată
- `user_settings` – grupă implicită + override tip săptămână
- `schedule_imported` – flag import inițial din config

---

## Dependențe

```
aiogram==3.7.0      # Framework Telegram bot (async)
openpyxl==3.1.2     # Generare Excel
PyYAML==6.0.1       # Citire configurare
pytz==2024.1        # Timezone Europe/Bucharest
aiosqlite==0.20.0   # SQLite async
```

---

## Deploy pe Ubuntu (Oracle Cloud / orice VM)

### 1. Pregătire sistem

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip git
```

### 2. Clonare/copiere proiect

```bash
cd /opt
sudo git clone https://github.com/DenMobile206/orar.git
sudo chown -R $USER:$USER /opt/orar
cd /opt/orar
```

### 3. Creare mediu virtual și instalare dependențe

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configurare token și whitelist

```bash
nano bot/config.yaml
```

Modifică:

```yaml
telegram:
  token: "TOKEN_BOT_TĂU"   # de la @BotFather

whitelist:
  - 123456789   # ID-ul tău Telegram (de la @userinfobot)
  - 987654321   # ID-ul colegului
```

### 5. Testare manuală

```bash
source venv/bin/activate
python bot/main.py
```

Trimite `/start` în bot ca să verifici că funcționează. `Ctrl+C` pentru oprire.

### 6. Configurare serviciu systemd (pornire automată)

Creează fișierul serviciu:

```bash
sudo nano /etc/systemd/system/orar-bot.service
```

Conținut:

```ini
[Unit]
Description=Orar Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/orar
ExecStart=/opt/orar/venv/bin/python bot/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

> Înlocuiește `ubuntu` cu utilizatorul tău real (`whoami`).

### 7. Activare și pornire serviciu

```bash
sudo systemctl daemon-reload
sudo systemctl enable orar-bot
sudo systemctl start orar-bot
```

### 8. Verificare status și loguri

```bash
# Status
sudo systemctl status orar-bot

# Loguri în timp real
sudo journalctl -u orar-bot -f

# Ultimele 100 linii de log
sudo journalctl -u orar-bot -n 100 --no-pager
```

### 9. Restart / Oprire

```bash
# Restart
sudo systemctl restart orar-bot

# Oprire
sudo systemctl stop orar-bot

# Dezactivare pornire automată
sudo systemctl disable orar-bot
```

### 10. Actualizare cod

```bash
cd /opt/orar
git pull
source venv/bin/activate
pip install -r requirements.txt  # dacă s-au schimbat dependențele
sudo systemctl restart orar-bot
```