# WarBoard: Vengeance

A fast tactical strategy prototype built in Python (Pygame). Pick countries, deploy tanks/troops/jets, place radar and AA, and launch missiles — including **Anti-Radar (AR)** missiles that **cannot be intercepted**. The AI takes **one action per round** to keep turns fair and readable.


---
Features
- Country picker with summarized capabilities
- **Missile combat** with range preview and area effect (radius)
- **AR/ARM missiles** that bypass AA
- **Radar + AA**: radar reveals; AA intercepts missiles/jets **in radar coverage**
- **Market**: buy units and systems mid-battle; purchases add directly to inventory
- **One action per round** (you and AI): move one unit **or** fire one missile
- Simple, readable animations (missiles, unit movement, explosions)

---

📦 Downloads
Grab the latest builds from **Releases**:  
- Windows: `WarBoard_Vengeance_v1_1_3_Windows.zip`  

---

## ▶️ Run from Source
```bash
# Windows (PowerShell)
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py

# Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
