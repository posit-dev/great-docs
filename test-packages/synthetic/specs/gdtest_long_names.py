"""
gdtest_long_names — Long object names to test sidebar wrapping.

Dimensions: A1, B1, C3, D1, E6, F6, G1, H7
Focus: Classes and methods with deliberately long, multi-segment names
       containing dots, underscores, camelCase, and deep nesting to
       exercise sidebar smart line-breaking.
"""

SPEC = {
    "name": "gdtest_long_names",
    "description": "Long object names for sidebar wrapping tests",
    "dimensions": ["A1", "B1", "C3", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-long-names",
            "version": "0.1.0",
            "description": "Test sidebar wrapping with long object names",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_long_names/__init__.py": '''\
            """Package with deliberately long object names."""

            __version__ = "0.1.0"

            from gdtest_long_names.store import (
                BaseDocumentStore,
                DuckDBDocumentStore,
                PostgreSQLDocumentStore,
            )
            from gdtest_long_names.embedding import (
                EmbeddingProvider,
                OpenAIEmbeddingProvider,
                CohereEmbeddingProvider,
            )
            from gdtest_long_names.chunker import (
                BaseChunkerStrategy,
                MarkdownChunkerStrategy,
            )
            from gdtest_long_names.types import (
                RetrievedDocumentChunk,
                DocumentMetadataConfig,
                EmbeddingVectorResult,
            )

            __all__ = [
                "BaseDocumentStore",
                "DuckDBDocumentStore",
                "PostgreSQLDocumentStore",
                "EmbeddingProvider",
                "OpenAIEmbeddingProvider",
                "CohereEmbeddingProvider",
                "BaseChunkerStrategy",
                "MarkdownChunkerStrategy",
                "RetrievedDocumentChunk",
                "DocumentMetadataConfig",
                "EmbeddingVectorResult",
            ]
        ''',
        "gdtest_long_names/store.py": '''\
            """Document store implementations."""


            class BaseDocumentStore:
                """
                Abstract base class for document stores.

                Parameters
                ----------
                connection_string
                    Database connection string.
                """

                def __init__(self, connection_string: str):
                    self.connection_string = connection_string

                def connect_to_database(self) -> None:
                    """Establish connection to the underlying database."""
                    pass

                def create_collection(self, name: str) -> None:
                    """Create a new document collection."""
                    pass


            class DuckDBDocumentStore(BaseDocumentStore):
                """
                DuckDB-backed document store with vector search.

                Parameters
                ----------
                connection_string
                    Database connection string.
                index_type
                    Type of vector index to use.
                """

                def __init__(self, connection_string: str, index_type: str = "hnsw"):
                    super().__init__(connection_string)
                    self.index_type = index_type

                def upsert_documents(self, docs: list) -> int:
                    """Insert or update documents in the store."""
                    return 0

                def ingest_from_directory(self, path: str) -> int:
                    """Ingest all documents from a directory."""
                    return 0

                def retrieve_by_similarity(self, query: str, top_k: int = 10) -> list:
                    """Retrieve documents by vector similarity search."""
                    return []

                def retrieve_by_bm25_score(self, query: str, top_k: int = 10) -> list:
                    """Retrieve documents using BM25 text scoring."""
                    return []

                def retrieve_hybrid_combination(self, query: str, top_k: int = 10) -> list:
                    """Retrieve using hybrid vector + BM25 combination."""
                    return []

                def build_vector_index(self) -> None:
                    """Build or rebuild the vector similarity index."""
                    pass

                def get_collection_size(self) -> int:
                    """Return the number of documents in the store."""
                    return 0


            class PostgreSQLDocumentStore(BaseDocumentStore):
                """
                PostgreSQL-backed document store with pgvector.

                Parameters
                ----------
                connection_string
                    Database connection string.
                embedding_dimension
                    Dimensionality of embedding vectors.
                """

                def __init__(self, connection_string: str, embedding_dimension: int = 1536):
                    super().__init__(connection_string)
                    self.embedding_dimension = embedding_dimension

                def upsert_with_embeddings(self, docs: list, embeddings: list) -> int:
                    """Insert or update documents with precomputed embeddings."""
                    return 0

                def retrieve_nearest_neighbors(self, embedding: list, top_k: int = 10) -> list:
                    """Retrieve documents using nearest neighbor search."""
                    return []

                def create_ivfflat_index(self, num_lists: int = 100) -> None:
                    """Create an IVFFlat index for approximate search."""
                    pass

                def vacuum_analyze_table(self) -> None:
                    """Run VACUUM ANALYZE on the document table."""
                    pass
        ''',
        "gdtest_long_names/embedding.py": '''\
            """Embedding provider implementations."""


            class EmbeddingProvider:
                """
                Base class for embedding providers.

                Parameters
                ----------
                model_name
                    Name of the embedding model.
                """

                def __init__(self, model_name: str):
                    self.model_name = model_name

                def generate_embeddings(self, texts: list) -> list:
                    """Generate embeddings for a list of texts."""
                    return []


            class OpenAIEmbeddingProvider(EmbeddingProvider):
                """
                OpenAI embedding provider using text-embedding models.

                Parameters
                ----------
                model_name
                    Name of the OpenAI model.
                api_key
                    OpenAI API key.
                """

                def __init__(self, model_name: str = "text-embedding-3-small", api_key: str = ""):
                    super().__init__(model_name)
                    self.api_key = api_key

                def generate_embeddings_batch(self, texts: list, batch_size: int = 100) -> list:
                    """Generate embeddings in batches to handle rate limits."""
                    return []

                def calculate_token_usage(self, texts: list) -> int:
                    """Calculate total token usage for a list of texts."""
                    return 0


            class CohereEmbeddingProvider(EmbeddingProvider):
                """
                Cohere embedding provider with input type support.

                Parameters
                ----------
                model_name
                    Name of the Cohere model.
                input_type
                    Type of input for embedding.
                """

                def __init__(self, model_name: str = "embed-english-v3.0", input_type: str = "search_document"):
                    super().__init__(model_name)
                    self.input_type = input_type

                def generate_with_input_type(self, texts: list, input_type: str) -> list:
                    """Generate embeddings with specific input type."""
                    return []

                def get_supported_languages(self) -> list:
                    """Return list of supported languages."""
                    return []
        ''',
        "gdtest_long_names/chunker.py": '''\
            """Chunker strategy implementations."""


            class BaseChunkerStrategy:
                """
                Abstract base class for document chunking strategies.

                Parameters
                ----------
                max_chunk_size
                    Maximum size of each chunk in characters.
                overlap_size
                    Number of overlapping characters between chunks.
                """

                def __init__(self, max_chunk_size: int = 1000, overlap_size: int = 200):
                    self.max_chunk_size = max_chunk_size
                    self.overlap_size = overlap_size

                def chunk_document_content(self, content: str) -> list:
                    """Split document content into chunks."""
                    return []

                def calculate_optimal_boundaries(self, content: str) -> list:
                    """Find optimal chunk boundary positions."""
                    return []


            class MarkdownChunkerStrategy(BaseChunkerStrategy):
                """
                Markdown-aware chunking strategy that respects heading boundaries.

                Parameters
                ----------
                max_chunk_size
                    Maximum size of each chunk in characters.
                overlap_size
                    Number of overlapping characters between chunks.
                preserve_code_blocks
                    Whether to keep code blocks intact.
                """

                def __init__(self, max_chunk_size: int = 1000, overlap_size: int = 200, preserve_code_blocks: bool = True):
                    super().__init__(max_chunk_size, overlap_size)
                    self.preserve_code_blocks = preserve_code_blocks

                def split_by_heading_hierarchy(self, content: str) -> list:
                    """Split content by markdown heading hierarchy."""
                    return []

                def merge_undersized_fragments(self, chunks: list) -> list:
                    """Merge chunks that are too small to stand alone."""
                    return []
        ''',
        "gdtest_long_names/types.py": '''\
            """Type definitions and data containers."""

            from dataclasses import dataclass


            @dataclass
            class RetrievedDocumentChunk:
                """
                A document chunk returned from a retrieval query.

                Parameters
                ----------
                content
                    The text content of the chunk.
                similarity_score
                    Cosine similarity score (0 to 1).
                document_id
                    Identifier of the source document.
                """

                content: str
                similarity_score: float
                document_id: str


            @dataclass
            class DocumentMetadataConfig:
                """
                Configuration for document metadata extraction.

                Parameters
                ----------
                extract_title
                    Whether to extract document titles.
                extract_author
                    Whether to extract author information.
                custom_metadata_fields
                    Additional metadata fields to extract.
                """

                extract_title: bool = True
                extract_author: bool = True
                custom_metadata_fields: list = None

                def __post_init__(self):
                    if self.custom_metadata_fields is None:
                        self.custom_metadata_fields = []


            @dataclass
            class EmbeddingVectorResult:
                """
                Result container for embedding vector operations.

                Parameters
                ----------
                vectors
                    List of embedding vectors.
                model_name
                    Name of the model used.
                token_count
                    Total tokens processed.
                """

                vectors: list
                model_name: str
                token_count: int
        ''',
    },
    "config": {
        "reference": {
            "sections": [
                {
                    "title": "Document Stores",
                    "desc": "Backend storage systems for documents and embeddings.",
                    "contents": [
                        "BaseDocumentStore",
                        "DuckDBDocumentStore",
                        "PostgreSQLDocumentStore",
                    ],
                },
                {
                    "title": "Embedding Providers",
                    "desc": "Services for generating vector embeddings.",
                    "contents": [
                        "EmbeddingProvider",
                        "OpenAIEmbeddingProvider",
                        "CohereEmbeddingProvider",
                    ],
                },
                {
                    "title": "Chunker Strategies",
                    "desc": "Strategies for splitting documents into chunks.",
                    "contents": [
                        "BaseChunkerStrategy",
                        "MarkdownChunkerStrategy",
                    ],
                },
                {
                    "title": "Data Types",
                    "desc": "Type definitions and result containers.",
                    "contents": [
                        "RetrievedDocumentChunk",
                        "DocumentMetadataConfig",
                        "EmbeddingVectorResult",
                    ],
                },
            ],
        },
        "sidebar_filter": {
            "enabled": True,
            "min_items": 1,
        },
    },
}
