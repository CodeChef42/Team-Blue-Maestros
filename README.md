# Team-Blue-Maestros
Official repository for Team Blue Maestros - Zayed Innovation Hackathon (IH25093)

# 🛡️ CrisisGuard — Local AI-Powered Ransomware Defense

**CrisisGuard** is a **lightweight, local-first cybersecurity framework** incorporating a **Python-based AI agent** and a **browser extension** to provide **non-cloud, real-time ransomware detection and recovery**.

With the application of **machine learning**, **offline encryption**, and **proactive web surveillance**, CrisisGuard isolates potential threats, restores files from safe backups, and denies ransomware infections from spreading.

---

## Features

### Local AI Detection (Python Agent)
- Monitors system directories and process activity in real-time.
- Detects abrupt file encryption, suspicious I/O, and CPU usage spikes.
- Employs **K-Means Clustering** and **Random Forest Classifier** to identify ransomware patterns.
- Generates **automatic encrypted offline backups** via AES encryption.
- Provides a **Flask/FastAPI** interface for communication with the browser extension.

### Browser Extension (HTML/CSS/JS)
- Checks URLs browsed and downloaded files for potential ransomware or phishing attacks.
- Passes suspicious URLs to the local Python AI for marking (non-malicious / malicious).
- Presents alerts and real-time system status in a popup UI.
- Syncs with the agent to enable adaptive learning from new patterns.

### Offline Secure Backups
- Stores encrypted offline copies of key files automatically.
- Enables one-click restore from the extension or local console.
- Uses AES-based secure storage to prevent tampering or unauthorized reading.

---

## Machine Learning & Data

CrisisGuard is trained on Kaggle ransomware and benign samples.
The model extracts behavior features with **pandas** (rename rates of files, access numbers, write bursts, etc.) and uses **scikit-learn** for classification.

**Algorithms Used:**
- **K-Means Clustering** — unsupervised anomaly detection and early threat detection.
- **Random Forest Classifier** — supervised classification of ransomware versus safe processes.

**Core Indicators:**
- File modification rate per second
- Renaming and frequency of deletion
- CPU and I/O bursts
- URL/domain reputation and frequency

---

## System Architecture

### Local Agent (Python)
- **Framework:** Flask / FastAPI
- **Responsibilities:**
  - Monitor file activity in real-time.
  - Run trained ML models to detect anomalies.
  - Create and store AES-encrypted offline backups.
  - Communicate with the browser extension via REST endpoints.

### Web Extension
- **Technologies:** HTML, CSS, JavaScript
- **Responsibilities:**
  - Scans URLs and downloads beforehand of access.
  - Submits URL data to the Python agent for analysis.
  - Displays system status, alerts, and restore options.

### Detection Logic
The agent utilizes a **multi-indicator scoring system** to scrutinize activity:
1. **File Activity Surge** — detects suspicious encryption-like activity.
2. **System Load Check** — looks for ransomware-type CPU and I/O spikes.
3. **Network Pattern** — monitors web traffic for suspicious domains.
4. **Decision Engine** — based on threat score, chooses:
   - Isolate process
   - Take encrypted backup
   - Alert user

---

## Workflow Overview

### Local Agent Workflow
1. Monitors user directories in real-time for bursts of file encryption or modification.
2. Extracts behavioral attributes and passes them to **K-Means** & **RandomForest** models.
3. If ransomware-like activity is found:
   - Malicious process is quarantined.
   - Safe offline backup is taken (AES-encrypted).
   - A recovery point is created.
4. Passes alert signal to browser extension UI.

### Browser Extension Workflow
1. Monitors visited websites and downloads.
2. Parses URLs and sends them to the Python agent API.
3. The agent determines whether they are **malicious** or **non-malicious** using AI models.
4. Displays warnings and blocks dangerous content before execution.

----

## Installation

### 1️⃣ Python Local Agent
```bash
git clone https://github.com/yourusername/CrisisGuard.git
cd CrisisGuard/agent
pip install -r requirements.txt
python agent.py
```
run python file ```detection3.py```

