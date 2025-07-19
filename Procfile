# Define os processos que o Railway deve rodar
worker: python -m app.main
results: python -m app.results_updater
auditor: python -m app.auditor
web: streamlit run python -m dashboard --server.port $PORT --server.address 0.0.0.0