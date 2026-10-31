import streamlit as st

st.set_page_config(page_title="Taktyka App", layout="wide")

st.title("Encyklopedia Taktyczna i Symulator Analogii")

tab1, tab2 = st.tabs(["Encyklopedia i Mapy", "Porównywarka i Symulator"])

with tab1:
    st.header("Baza bitew historycznych")
    st.write("Tu wkrótce pojawi się lista bitew i generowane mapy wektorowe na podstawie danych AI.")

with tab2:
    st.header("Symulator analogii taktycznych")
    st.write("Tutaj wpiszesz swój scenariusz, a my wyszukamy w bazie podobne starcia i wyciągniemy z nich wnioski.")
