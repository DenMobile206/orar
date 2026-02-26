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