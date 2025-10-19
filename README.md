# Team-Blue-Maestros
Official repository for team blue maestros - Zayed Innovation Hackathon

# 🛡️ CrisisGuard — Local AI-Powered Ransomware Defense

**CrisisGuard** is a **lightweight, local-first cybersecurity framework** that integrates a **Python-based AI agent** with a **browser extension** to provide **non-cloud, real-time ransomware detection and recovery**.  
By combining **machine learning**, **offline encryption**, and **proactive web monitoring**, CrisisGuard isolates potential threats, restores files from safe backups, and prevents ransomware infections before they spread.

---

## Features

### Local AI Detection (Python Agent)
- Monitors system directories and process behaviors in real-time.
- Detects rapid file encryption, abnormal I/O, and CPU bursts.
- Employs **K-Means Clustering** and **Random Forest Classifier** to identify ransomware patterns.
- Initiates **automatic encrypted offline backups** using AES encryption.
- Provides a **Flask/FastAPI** interface for communication with the browser extension.

### Browser Extension (HTML/CSS/JS)
- Scans visited URLs and downloaded files for potential ransomware or phishing attempts.
- Sends suspicious URLs to the local Python AI for classification (malicious / non-malicious).
- Displays alerts and live system status in a popup interface.
- Integrates with the agent to enable adaptive learning from new patterns.

### Offline Secure Backups
- Automatically maintains encrypted offline copies of important files.
- Enables one-click restore from the extension or local dashboard.
- Uses AES-based secure storage to prevent tampering or unauthorized access.

---

## Machine Learning & Data

CrisisGuard is trained using Kaggle ransomware and benign datasets.  
The model extracts behavioral features using **pandas** (file renaming rates, access frequency, write bursts, etc.) and leverages **scikit-learn** for classification.

**Algorithms Used:**
- **K-Means Clustering** — for unsupervised anomaly detection and early threat flagging.  
- **Random Forest Classifier** — for supervised classification of ransomware vs. safe processes.

**Core Indicators:**
- File modification rate per second  
- Frequency of renames and deletions  
- CPU and I/O bursts  
- URL/domain reputation and frequency  

---

## System Architecture

### Local Agent (Python)
- **Framework:** Flask / FastAPI  
- **Responsibilities:**
  - Monitors file activity in real-time.
  - Runs trained ML models to detect anomalies.
  - Creates and manages AES-encrypted offline backups.
  - Communicates with the browser extension via REST endpoints.

### Web Extension
- **Technologies:** HTML, CSS, JavaScript  
- **Responsibilities:**
  - Scans URLs and downloads before access.
  - Sends URL data to the Python agent for analysis.
  - Displays system status, alerts, and restore options.

### Detection Logic
The agent uses a **multi-indicator scoring system** to evaluate activity:
1. **File Activity Surge** — detects abnormal encryption-like behavior.  
2. **System Load Check** — monitors for ransomware-like CPU and I/O spikes.  
3. **Network Pattern** — inspects web activity for malicious domains.  
4. **Decision Engine** — based on threat score, chooses:
   - Isolate process  
   - Perform encrypted backup  
   - Notify user  

---

## Workflow Overview

### Local Agent Workflow
1. Watches user directories in real-time for file encryption or modification bursts.  
2. Extracts behavioral features and feeds them to **K-Means** & **RandomForest** models.  
3. If ransomware-like behavior is detected:
   - Suspicious process is isolated.  
   - Safe offline backup is created (AES-encrypted).  
   - A recovery point is established.  
4. Sends alert signal to browser extension UI.

### Browser Extension Workflow
1. Monitors visited websites and downloads.  
2. Extracts URLs and sends them to the Python agent API.  
3. The agent classifies them as **malicious** or **non-malicious** using AI models.  
4. Displays alerts and blocks dangerous content before execution.  

---

## Installation

### 1️⃣ Python Local Agent
```bash
git clone https://github.com/yourusername/CrisisGuard.git
cd CrisisGuard/agent
pip install -r requirements.txt
python agent.py
