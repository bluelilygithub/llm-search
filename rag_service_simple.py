#!/usr/bin/env python3
"""
Simplified RAG service that uses the existing context_items table
No need for a separate document_embeddings table!
"""

import json
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime
import openai
from sklearn.metrics.pairwise import cosine_similarity

class SimpleRAGService:
    def __init__(self, openai_api_key: str):
        """Initialize the RAG service"""
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        self.embedding_model = "text-embedding-3-small"
        self.chunk_size = 1000
        self.chunk_overlap = 200
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using OpenAI"""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {str(e)}")
            return None
    
    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """Split text into overlapping chunks"""
        if not text or len(text.strip()) == 0:
            return []
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                for i in range(end, max(start + self.chunk_size - 100, start), -1):
                    if text[i] in '.!?':
                        end = i + 1
                        break
            
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({
                    'text': chunk_text,
                    'start': start,
                    'end': end,
                    'metadata': {
                        'chunk_index': chunk_index,
                        'chunk_size': len(chunk_text)
                    }
                })
                chunk_index += 1
            
            # Move start position with overlap
            start = max(start + self.chunk_size - self.chunk_overlap, end)
        
        return chunks
    
    def process_document(self, context_item_id: str, text: str, metadata: Dict = None) -> bool:
        """Process a document: chunk it and generate embeddings, store in context_items.extra_data"""
        try:
            from models import ContextItem, db
            
            # Get the context item
            context_item = ContextItem.query.get(context_item_id)
            if not context_item:
                print(f"Context item {context_item_id} not found")
                return False
            
            # Check if already processed
            extra_data = context_item.extra_data or {}
            if extra_data.get('embeddings_processed'):
                print(f"Document {context_item.name} already processed")
                return True
            
            print(f"Processing document: {context_item.name}")
            print(f"Content length: {len(text)} characters")
            
            # Limit text size to prevent memory issues
            if len(text) > 50000:  # 50KB limit
                print(f"Document too large ({len(text)} chars), truncating to 50KB")
                text = text[:50000]
            
            # Chunk the text with smaller chunks
            chunks = self.chunk_text(text)
            if not chunks:
                print(f"No chunks generated for {context_item.name}")
                return False
            
            print(f"Generated {len(chunks)} chunks")
            
            # Limit number of chunks to prevent timeout (Railway has 30s limit)
            if len(chunks) > 10:
                print(f"Too many chunks ({len(chunks)}), limiting to 10 for Railway timeout")
                chunks = chunks[:10]
            
            # Generate embeddings for each chunk (with progress)
            chunk_embeddings = []
            for i, chunk in enumerate(chunks):
                print(f"Processing chunk {i+1}/{len(chunks)}...")
                
                # Limit chunk size
                chunk_text = chunk['text']
                if len(chunk_text) > 2000:
                    chunk_text = chunk_text[:2000]
                
                embedding = self.generate_embedding(chunk_text)
                if embedding:
                    chunk_embeddings.append({
                        'chunk_index': i,
                        'chunk_text': chunk_text,
                        'chunk_tokens': len(chunk_text.split()),
                        'embedding': embedding,
                        'metadata': {
                            **(metadata or {}),
                            **chunk['metadata'],
                            'start_char': chunk['start'],
                            'end_char': chunk['end']
                        }
                    })
                    print(f"  ✅ Chunk {i+1} processed")
                else:
                    print(f"  ❌ Chunk {i+1} failed")
            
            if not chunk_embeddings:
                print(f"No embeddings generated for {context_item.name}")
                return False
            
            print(f"Successfully generated {len(chunk_embeddings)} embeddings")
            
            # Store embeddings in extra_data
            extra_data['embeddings'] = chunk_embeddings
            extra_data['embeddings_processed'] = True
            extra_data['embeddings_processed_at'] = datetime.utcnow().isoformat()
            extra_data['total_chunks'] = len(chunk_embeddings)
            
            context_item.extra_data = extra_data
            db.session.commit()
            
            print(f"✅ Successfully processed {context_item.name}: {len(chunk_embeddings)} chunks")
            return True
            
        except Exception as e:
            print(f"❌ Error processing document {context_item_id}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def search_similar_chunks(self, query: str, similarity_threshold: float = 0.7, 
                            max_results: int = 10, user_id: str = None) -> List[Dict[str, Any]]:
        """Search for similar chunks using semantic similarity"""
        try:
            from models import ContextItem, db
            
            # Generate embedding for query
            query_embedding = self.generate_embedding(query)
            if query_embedding is None:
                return []
            
            # Get all processed documents
            query_filter = ContextItem.query.filter(
                ContextItem.content_type == 'document'
            )
            
            if user_id:
                query_filter = query_filter.filter(ContextItem.user_id == user_id)
            
            documents = query_filter.all()
            
            # Filter documents that have embeddings processed
            processed_documents = []
            for doc in documents:
                extra_data = doc.extra_data or {}
                if extra_data.get('embeddings_processed'):
                    processed_documents.append(doc)
            
            all_chunks = []
            
            # Extract chunks from each document
            for doc in processed_documents:
                extra_data = doc.extra_data or {}
                embeddings = extra_data.get('embeddings', [])
                
                for chunk_data in embeddings:
                    chunk_data['document_name'] = doc.name
                    chunk_data['document_description'] = doc.description
                    chunk_data['context_item_id'] = str(doc.id)
                    all_chunks.append(chunk_data)
            
            if not all_chunks:
                return []
            
            # Calculate similarities
            similarities = []
            for chunk in all_chunks:
                embedding = chunk['embedding']
                similarity = cosine_similarity([query_embedding], [embedding])[0][0]
                
                if similarity > similarity_threshold:
                    similarities.append({
                        'id': f"{chunk['context_item_id']}_{chunk['chunk_index']}",
                        'context_item_id': chunk['context_item_id'],
                        'chunk_text': chunk['chunk_text'],
                        'document_name': chunk['document_name'],
                        'document_description': chunk['document_description'],
                        'similarity_score': float(similarity),
                        'metadata': chunk['metadata']
                    })
            
            # Sort by similarity and limit results
            similarities.sort(key=lambda x: x['similarity_score'], reverse=True)
            return similarities[:max_results]
            
        except Exception as e:
            print(f"Error searching similar chunks: {str(e)}")
            return []
    
    def get_context_for_query(self, query: str, max_context_length: int = 4000, 
                            user_id: str = None) -> str:
        """Get relevant context for a query"""
        try:
            # Search for similar chunks
            results = self.search_similar_chunks(
                query=query,
                similarity_threshold=0.6,
                max_results=5,
                user_id=user_id
            )
            
            if not results:
                return ""
            
            # Build context string
            context_parts = []
            current_length = 0
            
            for result in results:
                chunk_text = result['chunk_text']
                document_name = result['document_name']
                similarity_score = result['similarity_score']
                
                # Format chunk with source info
                chunk_with_source = f"[From {document_name} (relevance: {similarity_score:.2f})]\n{chunk_text}\n"
                
                if current_length + len(chunk_with_source) > max_context_length:
                    break
                
                context_parts.append(chunk_with_source)
                current_length += len(chunk_with_source)
            
            return "\n".join(context_parts)
            
        except Exception as e:
            print(f"Error getting context for query: {str(e)}")
            return ""
    
    def process_all_documents(self, user_id: str = None) -> Dict[str, Any]:
        """Process all unprocessed documents (one at a time to prevent memory issues)"""
        try:
            from models import ContextItem, db
            
            # Get unprocessed documents
            query_filter = ContextItem.query.filter(
                ContextItem.content_type == 'document',
                ContextItem.content_text.isnot(None)
            )
            
            if user_id:
                query_filter = query_filter.filter(ContextItem.user_id == user_id)
            
            documents = query_filter.all()
            
            processed_count = 0
            error_count = 0
            
            print(f"Found {len(documents)} documents to process")
            
            for i, doc in enumerate(documents):
                try:
                    print(f"\n--- Processing document {i+1}/{len(documents)}: {doc.name} ---")
                    
                    # Check if already processed
                    extra_data = doc.extra_data or {}
                    if extra_data.get('embeddings_processed'):
                        print(f"Document {doc.name} already processed, skipping")
                        continue
                    
                    success = self.process_document(
                        context_item_id=str(doc.id),
                        text=doc.content_text,
                        metadata={
                            'document_name': doc.name,
                            'content_type': doc.content_type,
                            'created_at': doc.created_at.isoformat() if doc.created_at else None
                        }
                    )
                    
                    if success:
                        processed_count += 1
                        print(f"✅ Document {doc.name} processed successfully")
                    else:
                        error_count += 1
                        print(f"❌ Document {doc.name} failed to process")
                        
                except Exception as e:
                    print(f"❌ Error processing {doc.name}: {str(e)}")
                    error_count += 1
            
            print(f"\n📊 Processing Summary:")
            print(f"  ✅ Successfully processed: {processed_count}")
            print(f"  ❌ Errors: {error_count}")
            print(f"  📄 Total documents: {len(documents)}")
            
            return {
                'success': True,
                'processed_count': processed_count,
                'error_count': error_count,
                'total_documents': len(documents)
            }
            
        except Exception as e:
            print(f"❌ Error processing all documents: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
