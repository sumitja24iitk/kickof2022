# FIFA World Cup 2022 — Visual Analytics
#Tanmay Jain
CS661 course project. Interactive visual analytics web app built with Streamlit + Plotly
over StatsBomb open data for the 2022 FIFA World Cup.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Data

```bash
python scripts/fetch_data.py
```

## Run

```bash
streamlit run app.py
```
