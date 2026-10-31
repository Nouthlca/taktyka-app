import streamlit as st
import google.generativeai as genai
import folium
from streamlit_folium import st_folium
import os
import json

st.set_page_config(page_title="Taktyka App", layout="wide")
st.title("Encyklopedia Taktyczna i Symulator Analogii")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("Brak klucza API! Dodaj GEMINI_API_KEY w Portainerze.")
    st.stop()

genai.configure(api_key=api_key)

# Lista modeli od najlepszego do najbardziej niezawodnego "pewniaka"
dostepne_modele = [
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-pro"
]

tab1, tab2 = st.tabs(["Encyklopedia i Mapy", "Porównywarka i Symulator"])

with tab1:
    st.header("Baza bitew historycznych")
    bitwa = st.text_input("Wpisz nazwę bitwy (np. Bitwa pod Kurskiem):")
    
    if st.button("Analizuj bitwę"):
        if bitwa:
            with st.spinner("AI analizuje archiwa, sprawdza modele i przygotowuje mapę..."):
                prompt = f"""Jako ekspert wojskowy, opisz bitwę: {bitwa}.
                Zwróć wynik WYŁĄCZNIE jako poprawny JSON:
                {{
                    "opis": "Szczegółowy opis taktyki i przebiegu bitwy",
                    "lat": szerokość_geograficzna_jako_liczba,
                    "lon": długość_geograficzna_jako_liczba
                }}"""
                
                dane = None
                uzyty_model = ""
                
                # Kaskada: próbujemy każdego modelu po kolei
                for nazwa_modelu in dostepne_modele:
                    try:
                        model = genai.GenerativeModel(nazwa_modelu)
                        response = model.generate_content(prompt)
                        raw_text = response.text.strip().replace('```json', '').replace('```', '')
                        dane = json.loads(raw_text)
                        uzyty_model = nazwa_modelu
                        break  # Jeśli się udało, przerywamy pętlę!
                    except Exception:
                        continue  # Jeśli jest błąd 404, idziemy cicho do kolejnego modelu na liście
                
                if dane:
                    st.success(f"Udało się! Połączono przy użyciu modelu: {uzyty_model}")
                    st.write(dane["opis"])
                    
                    # Generowanie mapy
                    m = folium.Map(location=[dane["lat"], dane["lon"]], zoom_start=9)
                    folium.Marker([dane["lat"], dane["lon"]], popup=bitwa, icon=folium.Icon(color="red", icon="info-sign")).add_to(m)
                    st_folium(m, width=800, height=400)
                else:
                    st.error("Wszystkie modele AI z listy zawiodły. Sprawdź poprawność klucza API.")

with tab2:
    st.header("Symulator analogii taktycznych")
    st.write("Moduł dodamy w kolejnym kroku, gdy opanujemy generowanie map!")
