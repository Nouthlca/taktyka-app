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
            popup=folium.Popup(f"<b>{etykieta_strony}</b><br>Jednostka: {ruch.get('jednostka')}<br>Zadanie: {ruch.get('akcja')}", max_width=300),
            tooltip=f"{ruch.get('jednostka')} (Pozycja wyjściowa)",
            icon=folium.Icon(color=kolor_ikony, icon="flag", prefix="glyphicon")
        ).add_to(m)
        
        # Punkt docelowy / kierunek uderzenia
        folium.CircleMarker(
            location=[cel_lat, cel_lon],
            radius=6,
            color=kolor_linii,
            fill=True,
            fill_color="white",
            fill_opacity=1.0,
            tooltip=f"Cel/Rubież: {ruch.get('jednostka')} -> {ruch.get('akcja')}"
        ).add_to(m)
        
        # Animowany wektor ruchu (AntPath)
        plugins.AntPath(
            locations=[[s_lat, s_lon], [cel_lat, cel_lon]],
            dash_array=[10, 20],
            delay=800,
            color=kolor_linii,
            pulse_color="#ffffff",
            weight=5,
            opacity=0.85,
            tooltip=f"{ruch.get('jednostka')}: {ruch.get('akcja')}"
        ).add_to(m)

    # Opcjonalny marker punktu przełomowego
    if pokaz_przelom and punkt_przelomowy:
        p_lat = float(punkt_przelomowy.get("lat", c_lat))
        p_lon = float(punkt_przelomowy.get("lon", c_lon))
        folium.Marker(
            location=[p_lat, p_lon],
            popup=folium.Popup(f"<b>PUNKT PRZEŁOMOWY:</b><br>{punkt_przelomowy.get('tytul')}", max_width=300),
            tooltip=f"⭐ PUNKT PRZEŁOMOWY: {punkt_przelomowy.get('tytul')}",
            icon=folium.Icon(color="orange", icon="star", prefix="glyphicon")
        ).add_to(m)

    if len(wszystkie_wspolrzedne) > 1:
        m.fit_bounds(wszystkie_wspolrzedne, padding=(30, 30))

    folium.LayerControl(collapsed=False).add_to(m)
    return m

tab_encyklopedia, tab_symulator = st.tabs(["🗺️ Odprawa Taktyczna i Przebieg Operacji", "⚖️ Porównywarka i Symulator Analogii"])

with tab_encyklopedia:
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        bitwa = st.text_input("Wpisz nazwę bitwy lub operacji (np. Bitwa pod Kurskiem, Operacja Market Garden, Bitwa pod Kannami):", placeholder="np. Bitwa pod Kurskiem")
    with col_btn:
        st.write("")
        st.write("")
        uruchom = st.button("🔍 Generuj Odprawę Sztabową", use_container_width=True)

    if uruchom and bitwa:
        with st.spinner("Sztab AI analizuje archiwa, rozpisuje Ordre de Bataille, wektory natarcia i tabelę strat..."):
            prompt = f"""Jesteś starszym oficerem operacyjnym sztabu generalnego i historykiem wojskowości.
            Przygotuj kompletną, rygorystyczną odprawę taktyczno-historyczną dla starcia: {bitwa}.
            Opis ma być w języku polskim, nasycony konkretnymi nazwami związków taktycznych (dywizje, korpusy, brygady), typami uzbrojenia, ukształtowaniem terenu i godzinami.

            Zwróć wynik WYŁĄCZNIE jako poprawny obiekt JSON o dokładnie takiej strukturze:
            {{
                "tytul_operacji": "Pełna nazwa bitwy / kryptonim operacji",
                "data_i_rejon": "Dokładne daty oraz rejon geograficzny",
                "odprawa": {{
                    "rys_historyczny": "Szczegółowe tło strategiczne (3-4 akapity): dlaczego doszło do bitwy, sytuacja na froncie przed starciem.",
                    "strona_a": {{
                        "nazwa": "Nazwa państwa/koalicji A (na mapie oznaczana jako Niebiescy)",
                        "dowodcy": "Głównodowodzący oraz dowódcy kluczowych armii/korpusów",
                        "zadania_i_intencje": "Dokładny cel operacyjny, plan manewru, intencje sztabu przed bitwą",
                        "sily_poczatkowe": "Liczebność wojsk, liczba czołgów, dział, samolotów",
                        "dyslokacja": "Dokładne rozmieszczenie poszczególnych armii/korpusów przed godziną zero (Ordre de Bataille)"
                    }},
                    "strona_b": {{
                        "nazwa": "Nazwa państwa/koalicji B (na mapie oznaczana jako Czerwoni)",
                        "dowodcy": "Głównodowodzący oraz dowódcy kluczowych armii/korpusów",
                        "zadania_i_intencje": "Dokładny cel operacyjny, plan obrony/natarcia, intencje sztabu",
                        "sily_poczatkowe": "Liczebność wojsk, liczba czołgów, dział, samolotów, pasy umocnień",
                        "dyslokacja": "Dokładne rozmieszczenie poszczególnych armii/korpusów i odwodów przed starciem (Ordre de Bataille)"
                    }},
                    "punkt_przelomowy": {{
                        "tytul": "Nazwa kluczowego momentu przełomowego bitwy",
                        "czas_i_miejsce": "Dokładna data, godzina i miejscowość/rejon",
                        "szczegolowy_opis": "Bardzo dokładna, wielozdaniowa analiza taktyczna punktu kulminacyjnego: jak do niego doszło, jakie jednostki starły się bezpośrednio, jakie decyzje dowódców lub błędy przeważyły szalę.",
                        "konsekwencje": "Bezpośredni wpływ tego momentu na załamanie planu jednej ze stron i wynik całej operacji.",
                        "lat": 51.05,
                        "lon": 36.73
                    }}
                }},
                "fazy": [
                    {{
                        "numer": 1,
                        "czas": "Data i godzina (np. 5 lipca 1943, 02:20 - 06:00)",
                        "tytul": "Tytuł fazy operacji",
                        "opis_sytuacji": "Szczegółowy opis przebiegu walk w tej fazie: kto uderzył, gdzie nastąpiło przełamanie lub odparcie, jakie wsparcie ogniowe/lotnicze zadziałało.",
                        "co_sie_zmienia": "Krótki, punktowy wykaz zmian taktycznych na mapie w porównaniu do stanu poprzedniego (np. utrata pozycji X, wejście odwodów Y).",
                        "centrum_lat": 52.25,
                        "centrum_lon": 36.02,
                        "promien_walk_km": 20,
                        "ruchy_wojsk": [
                            {{
                                "strona": "A",
                                "jednostka": "Konkretna nazwa dywizji/korpusu Strony A",
                                "akcja": "Opis manewru (np. uderzenie przełamujące na Ponyri)",
                                "start_lat": 52.35,
                                "start_lon": 35.95,
                                "cel_lat": 52.25,
                                "cel_lon": 36.02
                            }},
                            {{
                                "strona": "B",
                                "jednostka": "Konkretna nazwa dywizji/korpusu Strony B",
                                "akcja": "Opis manewru (np. obrona ugrupowania głębokiego / kontratak)",
                                "start_lat": 52.20,
                                "start_lon": 36.05,
                                "cel_lat": 52.24,
                                "cel_lon": 36.02
                            }}
                        ]
                    }}
                ],
                "straty": [
                    {{
                        "strona": "Dokładna nazwa Strony A lub B",
                        "faza": "Nazwa lub czas fazy (np. Faza 1 / 5 lipca)",
                        "kategoria": "Broń pancerna / Piechota / Artyleria / Lotnictwo / Flota",
                        "jednostka_lub_sprzet": "Konkretny typ sprzętu lub związek taktyczny (np. Czołgi PzKpfw VI Tiger i Panther)",
                        "stan_poczatkowy": "Ile posiadano przed starciem (np. 200 maszyn w korpusie)",
                        "stracono": "Ile stracono bezpowrotnie i uszkodzono (np. 42 zniszczone, 80 uszkodzonych)",
                        "uwagi_taktyczne": "Od czego poniesiono straty (np. gęste pola minowe i ogień armat ZIS-3)"
                    }}
                ]
            }}
            WYMAGANIA:
            1. Wygeneruj minimum 5 chronologicznych faz w tablicy "fazy". W każdej fazie podaj od 2 do 4 obiektów w "ruchy_wojsk" z realnymi, różniącymi się współrzędnymi geograficznymi (start_lat/lon oraz cel_lat/lon), aby wektory na mapie pokazywały rzeczywisty ruch!
            2. Wygeneruj minimum 8-12 szczegółowych wierszy w tablicy "straty" dla obu stron i różnych kategorii sprzętu.
            """
            
            lista_do_testu = pobierz_dostepne_modele()
            dane = None
            uzyty_model = ""
            ostatni_blad = ""
            
            for nazwa_modelu in lista_do_testu:
                try:
                    model = genai.GenerativeModel(
                        nazwa_modelu,
                        safety_settings=safety_settings,
                        generation_config={"response_mime_type": "application/json"}
                    )
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
            
            if dane and "odprawa" in dane and "fazy" in dane:
                st.session_state["taktyka_dane"] = dane
                st.session_state["taktyka_model"] = uzyty_model
                st.session_state["taktyka_blad"] = None
            else:
                st.session_state["taktyka_dane"] = None
                st.session_state["taktyka_blad"] = ostatni_blad or "Model nie zwrócił pełnej struktury odprawy."

    if st.session_state.get("taktyka_blad"):
        st.error("Błąd generowania odprawy taktycznej.")
        st.warning(f"Szczegóły techniczne: {st.session_state['taktyka_blad']}")

    if st.session_state.get("taktyka_dane"):
        dane = st.session_state["taktyka_dane"]
        odprawa = dane.get("odprawa", {})
        strona_a = odprawa.get("strona_a", {})
        strona_b = odprawa.get("strona_b", {})
        przelom = odprawa.get("punkt_przelomowy", {})
        fazy = dane.get("fazy", [])
        straty_lista = dane.get("straty", [])

        st.success(f"Odprawa przygotowana przez sztab AI ({st.session_state['taktyka_model']}) | Operacja: {dane.get('tytul_operacji', bitwa)} ({dane.get('data_i_rejon', '')})")

        # GŁÓWNE ZAKŁADKI OPERACYJNE
        sub1, sub2, sub3, sub4 = st.tabs([
            "📋 1. Odprawa Sztabowa i Punkt Przełomowy",
            "🛡️ 2. Ordre de Bataille (Siły i Dyslokacja)",
            "⚔️ 3. Przebieg Bitwy i Mapa Wektorowa (Faza po fazie)",
            "📊 4. Rejestr Strat i Sprzętu (Tabela + Filtry)"
        ])

        # ZAKŁADKA 1: ODPRAWA I PUNKT PRZEŁOMOWY (OTWIERA SIĘ JAKO PIERWSZA)
        with sub1:
            st.subheader(f"📌 {dane.get('tytul_operacji', bitwa)} — {dane.get('data_i_rejon', '')}")
            
            with st.expander("📖 Rys Historyczny i Sytuacja Strategiczna (Rozwiń / Zwiń)", expanded=True):
                st.write(odprawa.get("rys_historyczny", "Brak danych."))

            with st.expander("🎖️ Dowództwo, Zadania Operacyjne i Intencje Stron", expanded=True):
                c_a, c_b = st.columns(2)
                with c_a:
                    st.markdown(f"""<div class="strona-a-box">
                        <h4>🔵 STRONA A: {strona_a.get('nazwa', 'Strona A')}</h4>
                        <p><b>Dowództwo:</b> {strona_a.get('dowodcy', '-')}</p>
                        <p><b>Intencje i zadania:</b> {strona_a.get('zadania_i_intencje', '-')}</p>
                    </div>""", unsafe_allow_html=True)
                with c_b:
                    st.markdown(f"""<div class="strona-b-box">
                        <h4>🔴 STRONA B: {strona_b.get('nazwa', 'Strona B')}</h4>
                        <p><b>Dowództwo:</b> {strona_b.get('dowodcy', '-')}</p>
                        <p><b>Intencje i zadania:</b> {strona_b.get('zadania_i_intencje', '-')}</p>
                    </div>""", unsafe_allow_html=True)

            st.markdown("### ⚡ Punkt Przełomowy (Kulminacyjny) Operacji")
            st.markdown(f"""<div class="przelom-box">
                <h3>⭐ {przelom.get('tytul', 'Punkt Kulminacyjny')}</h3>
                <p><b>⏱️ Czas i rejon:</b> {przelom.get('czas_i_miejsce', '-')}</p>
                <hr style="border-color: #ff4b4b;">
                <p><b>🔍 Szczegółowa analiza przebiegu:</b><br>{przelom.get('szczegolowy_opis', '-')}</p>
                <p><b>🎯 Konsekwencje operacyjne:</b><br>{przelom.get('konsekwencje', '-')}</p>
            </div>""", unsafe_allow_html=True)

        # ZAKŁADKA 2: ORDRE DE BATAILLE (SIŁY I GDZIE STAŁY)
        with sub2:
            st.subheader("🛡️ Siły Wyjściowe i Dyslokacja Związków Taktycznych przed Bitwą")
            col_ob_a, col_ob_b = st.columns(2)
            with col_ob_a:
                st.markdown(f"### 🔵 {strona_a.get('nazwa', 'Strona A')}")
                with st.expander("📦 Skład Sił i Uzbrojenie (Co mieli)", expanded=True):
                    st.write(strona_a.get("sily_poczatkowe", "-"))
                with st.expander("📍 Dyslokacja i Rejony Wyjściowe (Gdzie stali)", expanded=True):
                    st.write(strona_a.get("dyslokacja", "-"))
            with col_ob_b:
                st.markdown(f"### 🔴 {strona_b.get('nazwa', 'Strona B')}")
                with st.expander("📦 Skład Sił i Uzbrojenie (Co mieli)", expanded=True):
                    st.write(strona_b.get("sily_poczatkowe", "-"))
                with st.expander("📍 Dyslokacja i Rejony Wyjściowe (Gdzie stali)", expanded=True):
                    st.write(strona_b.get("dyslokacja", "-"))

        # ZAKŁADKA 3: PRZEBIEG WALK FAZA PO FAZIE + DYNAMICZNA MAPA
        with sub3:
            if fazy:
                st.subheader("⚔️ Chronologiczny Przebieg Walk i Aktualizacja Sytuacji na Mapie")
                opcje_faz = [f"Faza {f.get('numer', i+1)}: {f.get('czas', '')} — {f.get('tytul', '')}" for i, f in enumerate(fazy)]
                wybrana_etykieta = st.radio("Wybierz fazę operacji (kliknięcie aktualizuje mapę i wektory uderzeń):", opcje_faz, horizontal=True)
                idx_fazy = opcje_faz.index(wybrana_etykieta)
                aktywna_faza = fazy[idx_fazy]

                col_opis, col_mapa = st.columns([1, 1.4])
                with col_opis:
                    st.markdown(f"### ⏱️ {aktywna_faza.get('czas', '')}")
                    st.markdown(f"#### {aktywna_faza.get('tytul', '')}")
                    st.write(aktywna_faza.get("opis_sytuacji", ""))
                    
                    st.info(f"**🔄 Co się zmienia na polu bitwy:**\n\n{aktywna_faza.get('co_sie_zmienia', 'Brak danych.')}")
                    
                    with st.expander("🎯 Wykaz ruchów jednostek na mapie w tej fazie", expanded=True):
                        for r in aktywna_faza.get("ruchy_wojsk", []):
                            ikona = "🔵" if str(r.get("strona", "A")).upper() == "A" else "🔴"
                            st.markdown(f"- {ikona} **{r.get('jednostka')}**: {r.get('akcja')}")

                with col_mapa:
                    pokaz_gwiazdke = st.checkbox("Pokaż na mapie również lokalizację Punktu Przełomowego ⭐", value=True)
                    mapa_fazy = zbuduj_mape_taktyczna(aktywna_faza, przelom, pokaz_gwiazdke)
                    st_folium(mapa_fazy, width=850, height=620, key=f"mapa_faza_{idx_fazy}_{pokaz_gwiazdke}")

        # ZAKŁADKA 4: TABELA STRAT Z FILTROWANIEM
        with sub4:
            st.subheader("📊 Rejestr Strat Bojowych i Stanu Sprzętu")
            if straty_lista:
                df_straty = pd.DataFrame(straty_lista)
                # Ujednolicenie nazw kolumn
                kolumny_map = {
                    "strona": "Strona konfliktu",
                    "faza": "Kiedy (Faza / Czas)",
                    "kategoria": "Kategoria",
                    "jednostka_lub_sprzet": "Jednostka / Typ sprzętu",
                    "stan_poczatkowy": "Co mieli (Stan wyjściowy)",
                    "stracono": "Co stracili (Straty)",
                    "uwagi_taktyczne": "Przyczyna / Uwagi taktyczne"
                }
                df_straty = df_straty.rename(columns=kolumny_map)

                f_col1, f_col2, f_col3 = st.columns(3)
                with f_col1:
                    dostepne_strony = df_straty["Strona konfliktu"].unique().tolist() if "Strona konfliktu" in df_straty else []
                    filtr_strona = st.multiselect("Filtruj po stronie konfliktu:", dostepne_strony, default=dostepne_strony)
                with f_col2:
                    dostepne_kat = df_straty["Kategoria"].unique().tolist() if "Kategoria" in df_straty else []
                    filtr_kat = st.multiselect("Filtruj po kategorii sprzętu/wojsk:", dostepne_kat, default=dostepne_kat)
                with f_col3:
                    dostepne_fazy_strat = df_straty["Kiedy (Faza / Czas)"].unique().tolist() if "Kiedy (Faza / Czas)" in df_straty else []
                    filtr_faza = st.multiselect("Filtruj po fazie/czasie:", dostepne_fazy_strat, default=dostepne_fazy_strat)

                df_filtrowane = df_straty.copy()
                if "Strona konfliktu" in df_filtrowane and filtr_strona:
                    df_filtrowane = df_filtrowane[df_filtrowane["Strona konfliktu"].isin(filtr_strona)]
                if "Kategoria" in df_filtrowane and filtr_kat:
                    df_filtrowane = df_filtrowane[df_filtrowane["Kategoria"].isin(filtr_kat)]
                if "Kiedy (Faza / Czas)" in df_filtrowane and filtr_faza:
                    df_filtrowane = df_filtrowane[df_filtrowane["Kiedy (Faza / Czas)"].isin(filtr_faza)]

                st.dataframe(df_filtrowane, use_container_width=True, hide_index=True)
            else:
                st.write("Brak szczegółowych danych o stratach.")

with tab_symulator:
    st.header("⚖️ Symulator Analogii Taktycznych")
    st.write("Moduł porównywarki uruchomimy jako następny krok po zatwierdzeniu nowego widoku sztabowego.")
