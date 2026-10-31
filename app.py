import streamlit as st
import google.generativeai as genai
import folium
from folium import plugins
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

@st.cache_data(ttl=3600)
def pobierz_dostepne_modele():
    try:
        wszystkie = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        preferowane = [m for m in wszystkie if 'flash' in m or 'pro' in m]
        reszta = [m for m in wszystkie if m not in preferowane]
        return preferowane + reszta
    except Exception:
        return []

tab1, tab2 = st.tabs(["Encyklopedia i Mapy", "Porównywarka i Symulator"])

with tab1:
    st.header("Baza bitew historycznych")
    modele_z_api = pobierz_dostepne_modele()
    
    bitwa = st.text_input("Wpisz nazwę bitwy (np. Bitwa pod Kurskiem, Operacja Market Garden):")
    
    if st.button("Analizuj bitwę") and bitwa:
        with st.spinner("AI analizuje przebieg taktyczny, wektory natarcia i przygotowuje animowaną mapę..."):
            prompt = f"""Jako ekspert wojskowy, zrób zaawansowaną analizę taktyczną starcia: {bitwa}.
            Zależy mi na precyzyjnej, chronologicznej osi czasu (godzina po godzinie lub faza po fazie).
            Zwróć wynik WYŁĄCZNIE jako poprawny JSON o następującej strukturze (żadnego dodatkowego tekstu):
            {{
                "fazy": [
                    {{
                        "czas": "np. 04:30",
                        "tytul": "Krótki tytuł manewru",
                        "opis": "Dokładny opis taktyczny ruchów wojsk, wykorzystanego sprzętu i starć...",
                        "lat": 51.73,
                        "lon": 36.19
                    }}
                ]
            }}
            W polach lat i lon wpisz szerokość i długość geograficzną jako liczby. Wygeneruj od 4 do 7 kluczowych faz operacji z różnymi współrzędnymi geograficznymi, aby ukazać realny ruch wojsk na mapie."""
            
            lista_do_testu = modele_z_api if modele_z_api else ["models/gemini-2.5-flash", "models/gemini-2.0-flash", "models/gemini-1.5-pro"]
            dane = None
            uzyty_model = ""
            ostatni_blad = ""
            
            for nazwa_modelu in lista_do_testu:
                try:
                    model = genai.GenerativeModel(nazwa_modelu, safety_settings=safety_settings)
                    response = model.generate_content(prompt)
                    raw_text = response.text.strip()
                    
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
            
            if dane and "fazy" in dane:
                st.session_state["wynik_dane"] = dane
                st.session_state["wynik_model"] = uzyty_model
                st.session_state["wynik_bitwa"] = bitwa
                st.session_state["wynik_blad"] = None
            else:
                st.session_state["wynik_dane"] = None
                st.session_state["wynik_blad"] = ostatni_blad or "Błędny format JSON."

    if st.session_state.get("wynik_blad"):
        st.error("Wszystkie modele AI zawiodły lub zwróciły błędne dane.")
        st.warning(f"Szczegóły: {st.session_state['wynik_blad']}")
        
    if st.session_state.get("wynik_dane"):
        dane = st.session_state["wynik_dane"]
        fazy = dane["fazy"]
        st.success(f"Raport wygenerowany przez model: {st.session_state['wynik_model']}")
        
        # Inicjalizacja ciemnej mapy z pierwszej współrzędnej
        start_lat = float(fazy[0]["lat"])
        start_lon = float(fazy[0]["lon"])
        m = folium.Map(location=[start_lat, start_lon], zoom_start=8, tiles="CartoDB dark_matter")
        
        punkty = []
        col1, col2 = st.columns([1, 1.5]) # Lewa kolumna węższa (tekst), prawa szersza (mapa)
        
        with col1:
            st.subheader(f"Przebieg operacji: {st.session_state['wynik_bitwa']}")
            for i, faza in enumerate(fazy):
                lat = float(faza["lat"])
                lon = float(faza["lon"])
                punkty.append([lat, lon])
                
                # Marker na mapie
                folium.Marker(
                    [lat, lon],
                    popup=f"Faza {i+1}: {faza['tytul']}",
                    tooltip=faza['czas'],
                    icon=folium.Icon(color="red", icon="screenshot", prefix='glyphicon')
                ).add_to(m)
                
                # Zapis na ekranie (oś czasu)
                st.markdown(f"**[{faza['czas']}] - {faza['tytul']}**")
                st.write(faza["opis"])
                st.divider()
                
        with col2:
            # Animowana ścieżka natarcia łącząca punkty
            if len(punkty) > 1:
                plugins.AntPath(
                    locations=punkty, 
                    dash_array=[10, 20], 
                    color="red", 
                    pulse_color="white",
                    weight=4,
                    opacity=0.8
                ).add_to(m)
                
            st_folium(m, width=800, height=700)

with tab2:
    st.header("Symulator analogii taktycznych")
    st.write("Moduł dodamy w kolejnym kroku, gdy opanujemy generowanie map!")
