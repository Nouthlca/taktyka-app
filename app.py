import streamlit as st
import google.generativeai as genai
import folium
from streamlit_folium import st_folium
import os
import json
from google.generativeai.types import HarmCategory, HarmBlockThreshold

st.set_page_config(page_title="Taktyka App", layout="wide")
st.title("Encyklopedia Taktyczna i Symulator Analogii")

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

# Automatyczne pobieranie listy modeli aktualnie działających na Twoim kluczu
@st.cache_data(ttl=3600)
def pobierz_dostepne_modele():
    try:
        wszystkie = [
            m.name for m in genai.list_models()
            if 'generateContent' in m.supported_generation_methods
        ]
        preferowane = [m for m in wszystkie if 'flash' in m or 'pro' in m]
        reszta = [m for m in wszystkie if m not in preferowane]
        return preferowane + reszta
    except Exception:
        return []

tab1, tab2 = st.tabs(["Encyklopedia i Mapy", "Porównywarka i Symulator"])

with tab1:
    st.header("Baza bitew historycznych")
    
    modele_z_api = pobierz_dostepne_modele()
    if modele_z_api:
        st.caption(f"Dostępne modele na Twoim kluczu: {', '.join(modele_z_api[:4])}")
    
    bitwa = st.text_input("Wpisz nazwę bitwy (np. Bitwa pod Kurskiem):")
    
    if st.button("Analizuj bitwę") and bitwa:
        with st.spinner("AI analizuje archiwa i przygotowuje mapę..."):
            prompt = f"""Jako ekspert wojskowy, opisz bitwę: {bitwa}.
            Zwróć wynik WYŁĄCZNIE jako poprawny JSON (bez żadnego dodatkowego tekstu):
            {{
                "opis": "Szczegółowy opis taktyki i przebiegu bitwy",
                "lat": 51.73,
                "lon": 36.19
            }}
            W polach lat i lon wpisz dokładne współrzędne geograficzne tej bitwy jako liczby."""
            
            lista_do_testu = modele_z_api if modele_z_api else [
                "models/gemini-2.5-flash",
                "models/gemini-2.5-pro",
                "models/gemini-2.0-flash"
            ]
            
            dane = None
            uzyty_model = ""
            ostatni_blad = ""
            
            for nazwa_modelu in lista_do_testu:
                try:
                    model = genai.GenerativeModel(nazwa_modelu, safety_settings=safety_settings)
                    response = model.generate_content(prompt)
                    raw_text = response.text.strip()
                    
                    # Wyciąganie czystego formatu JSON z odpowiedzi modelu
                    start = raw_text.find('{')
                    end = raw_text.rfind('}') + 1
                    if start != -1 and end != 0:
                        raw_text = raw_text[start:end]
                        
                    dane = json.loads(raw_text)
                    uzyty_model = nazwa_modelu
                    break
                except Exception as e:
                    ostatni_blad = f"{nazwa_modelu} -> {str(e)}"
                    continue
            
            if dane:
                st.session_state["wynik_dane"] = dane
                st.session_state["wynik_model"] = uzyty_model
                st.session_state["wynik_bitwa"] = bitwa
                st.session_state["wynik_blad"] = None
            else:
                st.session_state["wynik_dane"] = None
                st.session_state["wynik_blad"] = ostatni_blad

    if st.session_state.get("wynik_blad"):
        st.error("Wszystkie modele AI z listy zawiodły.")
        st.warning(f"Treść ostatniego błędu: {st.session_state['wynik_blad']}")
        
    if st.session_state.get("wynik_dane"):
        dane = st.session_state["wynik_dane"]
        st.success(f"Połączono przy użyciu modelu: {st.session_state['wynik_model']}")
        st.write(dane["opis"])
        
        lat = float(dane["lat"])
        lon = float(dane["lon"])
        m = folium.Map(location=[lat, lon], zoom_start=9)
        folium.Marker(
            [lat, lon], 
            popup=st.session_state["wynik_bitwa"], 
            icon=folium.Icon(color="red", icon="info-sign")
        ).add_to(m)
        st_folium(m, width=800, height=400)

with tab2:
    st.header("Symulator analogii taktycznych")
    st.write("Moduł dodamy w kolejnym kroku, gdy opanujemy generowanie map!")
