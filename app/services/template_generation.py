from dataclasses import dataclass


@dataclass
class GeneratedDocumentMetadata:
    filename: str
    content_type: str
    notes: str


class TemplateGenerationService:
    def generate_document(self, event_id: int, document_type_id: int, context: dict) -> GeneratedDocumentMetadata:
        return GeneratedDocumentMetadata(
            filename=f"event_{event_id}_doc_type_{document_type_id}.txt",
            content_type="text/plain",
            notes="TODO: implement DOCX/XLSX template generation pipeline",
        )
