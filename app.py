import streamlit as st
import google.generativeai as genai
import folium
from folium import plugins
from streamlit_folium import st_folium
import pandas as pd
import os
import json
from google.generativeai.types import HarmCategory, HarmBlockThreshold

st.set_page_config(page_title="System Odpraw Taktycznych C2", layout="wide")

# Stylizacja na wojskowy panel sztabowy
st.markdown("""
<style>
    .przelom-box {
        background-color: #2b1d1d;
        color: #f8f9fa;
        padding: 20px;
        border-left: 6px solid #ff4b4b;
        border-radius: 6px;
        margin-bottom: 20px;
    }
    .strona-a-box {
        background-color: #162636;
        color: #f8f9fa;
        padding: 15px;
        border-top: 4px solid #3b8ed0;
        border-radius: 6px;
    }
    .strona-b-box {
        background-color: #361616;
        color: #f8f9fa;
        padding: 15px;
        border-top: 4px solid #e03c3c;
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🎖️ Sztabowy System Analiz Taktycznych i Symulator Analogii")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("Brak klucza API! Dodaj GEMINI_API_KEY w Portainerze.")
    st.stop()

genai.configure(api_key=api_key)

safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

@st.cache_data(ttl=3600)
def pobierz_dostepne_modele():
    try:
        wszystkie = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Priorytet dla najnowszych modeli 2.5 Pro i Flash
        priorytet = [m for m in wszystkie if '2.5-flash' in m or '2.5-pro' in m or '2.0-flash' in m]
        reszta = [m for m in wszystkie if m not in priorytet and ('flash' in m or 'pro' in m)]
        return priorytet + reszta
    except Exception:
        return ["models/gemini-2.5-flash", "models/gemini-2.5-pro", "models/gemini-flash-latest"]

def zbuduj_mape_taktyczna(faza_dane, punkt_przelomowy=None, pokaz_przelom=False):
    c_lat = float(faza_dane.get("centrum_lat", 51.73))
    c_lon = float(faza_dane.get("centrum_lon", 36.19))
    
    m = folium.Map(location=[c_lat, c_lon], zoom_start=9, tiles=None)
    
    # Darmowe podkłady Esri (brak wymogu klucza API, alfabet łaciński)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Esri Topo",
        name="1. Mapa Sztabowa (Topograficzna - Łacińska)",
        control=True
    ).add_to(m)
    
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        attr="Esri Dark",
        name="2. Ciemna Mapa Dowodzenia (C2)",
        control=True
    ).add_to(m)
    
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri Sat",
        name="3. Zdjęcia Satelitarne Terenu",
        control=True
    ).add_to(m)

    wszystkie_wspolrzedne = [[c_lat, c_lon]]

    # Okrąg oznaczający główny rejon walk w danej fazie
    promien_m = float(faza_dane.get("promien_walk_km", 15)) * 1000
    folium.Circle(
        location=[c_lat, c_lon],
        radius=promien_m,
        color="#ff9900",
        weight=2,
        fill=True,
        fill_color="#ff9900",
        fill_opacity=0.12,
        tooltip=f"Rejon walk: {faza_dane.get('tytul', '')}"
    ).add_to(m)

    # Rysowanie wektorów natarcia i pozycji jednostek
    for ruch in faza_dane.get("ruchy_wojsk", []):
        s_lat = float(ruch.get("start_lat", c_lat))
        s_lon = float(ruch.get("start_lon", c_lon))
        cel_lat = float(ruch.get("cel_lat", c_lat))
        cel_lon = float(ruch.get("cel_lon", c_lon))
        
        wszystkie_wspolrzedne.extend([[s_lat, s_lon], [cel_lat, cel_lon]])
        
        czy_strona_a = str(ruch.get("strona", "A")).upper() == "A"
        kolor_linii = "#1f77b4" if czy_strona_a else "#d62728"
        kolor_ikony = "blue" if czy_strona_a else "red"
        etykieta_strony = "STRONA A (Niebiescy)" if czy_strona_a else "STRONA B (Czerwoni)"
        
        # Pozycja wyjściowa związku taktycznego
        folium.Marker(
            location=[s_lat, s_lon],
            popup=folium.Popup(f"<b>{etykieta_strony}</b><br>Jednostka: {ruch.get('jednostka')}<br>Zadanie: {ruch.get('akcja')}", max_width=3
