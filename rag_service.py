import openai
import numpy as np
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from models import ContextItem, DocumentEmbedding, db
import json
import re
from datetime import datetime

class RAGService:
    def __init__(self, openai_api_key: str):
        """Initialize RAG service with OpenAI API key"""
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        self.embedding_model = "text-embedding-3-small"  # Cost-effective embedding model
        self.chunk_size = 1000  # Characters per chunk
        self.chunk_overlap = 200  # Overlap between chunks
    
    def chunk_text(self, text: str, chunk_size: int = None, overlap: int = None) -> List[Dict[str, Any]]:
        """Split text into overlapping chunks for embedding"""
        chunk_size = chunk_size or self.chunk_size
        overlap = overlap or self.chunk_overlap
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at sentence boundaries
            if end < len(text):
                # Look for sentence endings within the last 100 characters
                sentence_end = text.rfind('.', start, end)
                if sentence_end > start + chunk_size - 100:
                    end = sentence_end + 1
            
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({
                    'text': chunk_text,
                    'start': start,
                    'end': end,
                    'metadata': {
                        'chunk_index': len(chunks),
                        'total_chunks': 0  # Will be updated later
                    }
                })
            
            start = end - overlap
        
        # Update total_chunks for all chunks
        for chunk in chunks:
            chunk['metadata']['total_chunks'] = len(chunks)
        
        return chunks
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI"""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return None
    
    def process_document(self, context_item_id: str, text: str, metadata: Dict = None) -> bool:
        """Process a document: chunk it and generate embeddings"""
        try:
            # Check if document already processed
            existing_embeddings = DocumentEmbedding.query.filter_by(context_item_id=context_item_id).first()
            if existing_embeddings:
                print(f"Document {context_item_id} already processed, skipping...")
                return True
            
            # Chunk the text
            chunks = self.chunk_text(text)
            
            # Generate embeddings for each chunk
            for chunk in chunks:
                embedding = self.generate_embedding(chunk['text'])
                if embedding is None:
                    continue
                
                # Create document embedding record
                doc_embedding = DocumentEmbedding(
                    context_item_id=context_item_id,
                    chunk_index=chunk['metadata']['chunk_index'],
                    chunk_text=chunk['text'],
                    chunk_tokens=len(chunk['text'].split()),  # Rough token count
                    embedding=embedding,
                    metadata={
                        **(metadata or {}),
                        **chunk['metadata'],
                        'start_char': chunk['start'],
                        'end_char': chunk['end']
                    }
                )
                
                db.session.add(doc_embedding)
            
            db.session.commit()
            print(f"Successfully processed document {context_item_id} into {len(chunks)} chunks")
            return True
            
        except Exception as e:
            print(f"Error processing document {context_item_id}: {e}")
            db.session.rollback()
            return False
    
    def search_similar_chunks(self, query: str, similarity_threshold: float = 0.7, 
                            max_results: int = 10, user_id: str = None) -> List[Dict[str, Any]]:
        """Search for similar chunks using semantic similarity"""
        try:
            # Generate embedding for query
            query_embedding = self.generate_embedding(query)
            if query_embedding is None:
                return []
            
            # Convert to JSON format for PostgreSQL
            embedding_json = json.dumps(query_embedding)
            
            # Build query with user filtering using cosine similarity function
            base_query = """
                SELECT 
                    de.id,
                    de.context_item_id,
                    de.chunk_text,
                    de.metadata,
                    ci.name as document_name,
                    ci.description as document_description,
                    cosine_similarity(de.embedding, %s::jsonb) as similarity_score
                FROM document_embeddings de
                JOIN context_items ci ON de.context_item_id = ci.id
                WHERE cosine_similarity(de.embedding, %s::jsonb) > %s
            """
            
            params = [embedding_json, embedding_json, similarity_threshold]
            
            # Add user filtering if provided
            if user_id:
                base_query += " AND ci.user_id = %s"
                params.append(user_id)
            
            base_query += " ORDER BY cosine_similarity(de.embedding, %s::jsonb) DESC LIMIT %s"
            params.extend([embedding_json, max_results])
            
            # Execute query
            result = db.session.execute(base_query, params)
            
            # Format results
            results = []
            for row in result:
                results.append({
                    'id': str(row.id),
                    'context_item_id': str(row.context_item_id),
                    'chunk_text': row.chunk_text,
                    'document_name': row.document_name,
                    'document_description': row.document_description,
                    'similarity_score': float(row.similarity_score),
                    'metadata': row.metadata
                })
            
            return results
            
        except Exception as e:
            print(f"Error searching similar chunks: {e}")
            return []
    
    def get_context_for_query(self, query: str, max_context_length: int = 4000, 
                            user_id: str = None) -> str:
        """Get relevant context for a query to include in AI response"""
        try:
            # Search for similar chunks
            similar_chunks = self.search_similar_chunks(
                query=query,
                similarity_threshold=0.6,
                max_results=20,
                user_id=user_id
            )
            
            if not similar_chunks:
                return ""
            
            # Build context string
            context_parts = []
            current_length = 0
            
            for chunk in similar_chunks:
                chunk_text = f"[From: {chunk['document_name']}]\n{chunk['chunk_text']}\n\n"
                
                if current_length + len(chunk_text) > max_context_length:
                    break
                
                context_parts.append(chunk_text)
                current_length += len(chunk_text)
            
            return "".join(context_parts)
            
        except Exception as e:
            print(f"Error getting context for query: {e}")
            return ""
    
    def process_all_documents(self, user_id: str = None) -> Dict[str, Any]:
        """Process all unprocessed documents in the database"""
        try:
            # Get all context items that haven't been processed
            query = db.session.query(ContextItem)
            if user_id:
                query = query.filter(ContextItem.user_id == user_id)
            
            context_items = query.filter(
                ContextItem.content_type.in_(['document', 'text']),
                ContextItem.is_active == True
            ).all()
            
            processed_count = 0
            error_count = 0
            
            for item in context_items:
                if item.content_text:
                    success = self.process_document(
                        context_item_id=str(item.id),
                        text=item.content_text,
                        metadata={
                            'document_name': item.name,
                            'content_type': item.content_type,
                            'created_at': item.created_at.isoformat() if item.created_at else None
                        }
                    )
                    
                    if success:
                        processed_count += 1
                    else:
                        error_count += 1
            
            return {
                'total_items': len(context_items),
                'processed_count': processed_count,
                'error_count': error_count,
                'success': True
            }
            
        except Exception as e:
            print(f"Error processing all documents: {e}")
            return {
                'total_items': 0,
                'processed_count': 0,
                'error_count': 0,
                'success': False,
                'error': str(e)
            }
