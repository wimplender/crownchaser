# 🚴 CrownChaser

CrownChaser is a Streamlit app to help you discover Strava segments near you that you *might* be able to crown, based on your FTP (Functional Threshold Power).

## 🌍 Features

- Explore segments near any location
- Intelligent caching of segment data and KOM times
- Filters for uphill and paved roads
- Estimates the power needed to beat the current KOM
- Highlights segments that might be within your reach 🚴‍♂️

## 📦 How to run locally

1. Clone the repo:
   ```bash
   git clone https://github.com/your-username/crownchaser.git
   cd crownchaser

pip install -r requirements.txt

STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret

streamlit run app.py
