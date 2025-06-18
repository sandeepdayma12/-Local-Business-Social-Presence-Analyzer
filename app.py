import streamlit as st
import pandas as pd
from analyzer.scraper import scrape_businesses  # Make sure this exists and works correctly

st.set_page_config(page_title="Local Business Analyzer", layout="wide")
st.title("📊 Local Business Social Presence Analyzer")

# Input section
city = st.text_input("Enter City Name", "Pune")
keyword = st.text_input("Enter Business Keyword", "Cafe")

if st.button("Search"):
    with st.spinner("🔍 Scraping data... please wait"):
        results = scrape_businesses(city, keyword)

        if results:
            st.success(f"✅ {len(results)} businesses found.")

            # Convert to DataFrame
            df = pd.DataFrame(results)

            # Optional filters
            show_no_website = st.checkbox("Show only businesses without Website")
            show_no_linkedin = st.checkbox("Show only businesses without LinkedIn")

            # Apply filters safely
            if show_no_website:
                df = df[df['website'].fillna('').str.strip().str.lower().isin(['', 'not found'])]

            if show_no_linkedin:
                df = df[df['linkedin'].fillna('').str.strip().str.lower().isin(['', 'not found'])]

            # Rename columns for display
            df_display = df.rename(columns={
                "name": "Business Name",
                "contact": "Contact",
                "website": "Website",
                "linkedin": "LinkedIn"
            })

            # Display DataFrame
            st.dataframe(df_display)

            # CSV Download Button
            csv = df_display.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name="business_results.csv",
                mime="text/csv"
            )
        else:
            st.warning("⚠️ No businesses found. Try changing the keyword or city.")
