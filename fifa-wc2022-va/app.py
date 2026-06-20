import streamlit as st

st.set_page_config(
    page_title="FIFA WC 2022 Visual Analytics",
    layout="wide",
)

with st.sidebar:
    st.header("Filters")
    st.selectbox("Team", options=["(all)"])
    st.selectbox("Match", options=["(all)"])

tab1, tab2, tab3, tab4 = st.tabs(["Tournament", "Match", "Player", "Tactical"])

with tab1:
    st.info("Tab 1 — Tournament overview coming in Phase 2")

with tab2:
    st.info("Tab 2 — Match analysis coming in Phase 2")

with tab3:
    st.info("Tab 3 — Player profile coming in Phase 2")

with tab4:
    st.info("Tab 4 — Tactical / advanced analytics coming in Phase 2")

st.caption("FIFA WC 2022 Visual Analytics · CS661 Course Project")
