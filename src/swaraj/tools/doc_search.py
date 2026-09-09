"""Local Document Search using ChromaDB and FastEmbed."""

from pathlib import Path
from typing import List, Dict, Any, Optional
import hashlib


class DocumentSearch:
    """Local document search with ChromaDB and FastEmbed."""
    
    def __init__(self, persist_directory: Optional[str] = None, workspace_root: Optional[str] = None):
        target_dir = persist_directory or (Path(workspace_root) / "chroma" if workspace_root else "data/chroma")
        self.persist_directory = Path(target_dir)
        self._client = None
        self._collection = None
        self._available = False
        
        try:
            import chromadb
            self.persist_directory.mkdir(parents=True, exist_ok=True)
            if hasattr(chromadb, "PersistentClient"):
                self._client = chromadb.PersistentClient(path=str(self.persist_directory))
            else:
                self._client = chromadb.Client()
            self._available = True
        except Exception:
            self._client = None
            self._available = False
    
    @property
    def available(self) -> bool:
        return self._available and self._client is not None
    
    def create_collection(self, name: str = "documents") -> None:
        """Create or get a collection for indexing."""
        if not self._available:
            raise RuntimeError(
                "ChromaDB is not available. Install chromadb package."
            )
        
        try:
            self._collection = self._client.get_or_create_collection(name=name)
        except Exception as e:
            raise RuntimeError(f"Failed to create collection: {e}")

    def index_document(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Index a document into the default collection."""
        if not self._collection:
            self.create_collection()
        self.add_document(doc_id=doc_id, content=text, metadata=metadata)

    
    def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a document to the index."""
        if not self._available or not self._collection:
            raise RuntimeError("Search index not initialized. Call create_collection first.")
        
        try:
            from fastembed import TextEmbedding
            
            embedding_model = TextEmbedding()
            embeddings = list(embedding_model.embed([content]))
            
            doc_metadata = metadata or {}
            doc_metadata["doc_id"] = doc_id
            doc_metadata["content_hash"] = hashlib.sha256(content.encode()).hexdigest()[:16]
            
            self._collection.add(
                ids=[doc_id],
                embeddings=[embeddings[0].tolist()],
                metadatas=[doc_metadata],
                documents=[content],
            )
        
        except ImportError:
            raise RuntimeError(
                "FastEmbed is not available. Install fastembed package for local embeddings."
            )
        except Exception as e:
            raise RuntimeError(f"Failed to add document: {e}")
    
    def search(
        self,
        query: str,
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search for relevant documents."""
        if not self._available or not self._collection:
            raise RuntimeError("Search index not available")
        
        try:
            from fastembed import TextEmbedding
            
            embedding_model = TextEmbedding()
            query_embedding = list(embedding_model.embed([query]))[0]
            
            results = self._collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
            
            if not results["documents"] or not results["documents"][0]:
                return []
            
            formatted_results = []
            for i, doc in enumerate(results["documents"][0]):
                result = {
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None,
                }
                formatted_results.append(result)
            
            return formatted_results
        
        except ImportError:
            raise RuntimeError(
                "FastEmbed is not available. Cannot perform search without embeddings."
            )
        except Exception as e:
            raise RuntimeError(f"Search failed: {e}")
    
    def get_source_references(self, doc_ids: List[str]) -> List[Dict[str, Any]]:
        """Retrieve source metadata for given document IDs."""
        if not self._collection:
            return []
        
        references = []
        for doc_id in doc_ids:
            try:
                result = self._collection.get(ids=[doc_id])
                if result["metadatas"]:
                    references.append({
                        "doc_id": doc_id,
                        "metadata": result["metadatas"][0],
                    })
            except Exception:
                continue
        
        return references


DocumentSearchTool = DocumentSearch
