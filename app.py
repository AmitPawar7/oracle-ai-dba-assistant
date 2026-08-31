import streamlit as st

from awr_engine import analyze_awr_report


st.set_page_config(
    page_title="Oracle AI DBA Assistant",
    page_icon="???",
    layout="wide",
)


st.title("??? Oracle AI DBA Assistant")

st.write(
    "Upload an Oracle AWR report and ask questions "
    "about its performance findings."
)


uploaded_file = st.file_uploader(
    "Upload AWR Report",
    type=["txt"],
)


if uploaded_file:
    st.success(
        f"Loaded: {uploaded_file.name}"
    )

    question = st.text_input(
        "Ask your Oracle DBA question",
        placeholder=(
            "e.g. What are the recommended DBA actions?"
        ),
    )

    if st.button(
        "Analyze",
        type="primary",
    ):
        if not question.strip():
            st.warning(
                "Please enter a question."
            )

        else:
            report_text = uploaded_file.getvalue().decode(
                "utf-8",
                errors="ignore",
            )

            with st.spinner(
                "Analyzing AWR report..."
            ):
                try:
                    answer = analyze_awr_report(
                        report_text,
                        question,
                        report_name=uploaded_file.name,
                    )

                    st.subheader("DBA Analysis")

                    st.text(answer)

                except Exception as exc:
                    st.error(
                        f"Analysis failed: {exc}"
                    )
