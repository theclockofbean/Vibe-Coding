import argparse
from app.agent.rag.ingestion_service import build_default_ingestion_service

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--source-type", default="qa")
    parser.add_argument("--recreate", action="store_true")

    args = parser.parse_args()

    service = build_default_ingestion_service()

    result = service.ingest(
        file_path=args.file,
        domain=args.domain,
        source_type=args.source_type,
        recreate=args.recreate
    )

    print(result)


if __name__ == "__main__":
    main()
