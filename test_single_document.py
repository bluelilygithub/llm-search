#!/usr/bin/env python3
"""
Test script to process a single document and debug issues
"""

import os
import sys
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, ContextItem
from rag_service_simple import SimpleRAGService

def test_single_document():
    """Test processing a single document"""
    
    with app.app_context():
        try:
            # Get the first document
            document = ContextItem.query.filter_by(content_type='document').first()
            
            if not document:
                print("❌ No documents found")
                return
            
            print(f"📄 Testing with document: {document.name}")
            print(f"📄 Document ID: {document.id}")
            print(f"📄 Content length: {len(document.content_text or '')} characters")
            
            # Check if already processed
            extra_data = document.extra_data or {}
            if extra_data.get('embeddings_processed'):
                print("✅ Document already processed")
                return
            
            # Initialize RAG service
            rag_service = SimpleRAGService(openai_api_key=os.getenv('OPENAI_API_KEY'))
            
            # Test chunking first
            print("🔪 Testing text chunking...")
            chunks = rag_service.chunk_text(document.content_text)
            print(f"📊 Generated {len(chunks)} chunks")
            
            if not chunks:
                print("❌ No chunks generated")
                return
            
            # Test embedding generation for first chunk
            print("🧠 Testing embedding generation...")
            first_chunk = chunks[0]['text']
            embedding = rag_service.generate_embedding(first_chunk)
            
            if embedding:
                print(f"✅ Embedding generated: {len(embedding)} dimensions")
            else:
                print("❌ Embedding generation failed")
                return
            
            # Process the document
            print("⚙️ Processing document...")
            success = rag_service.process_document(
                context_item_id=str(document.id),
                text=document.content_text,
                metadata={
                    'document_name': document.name,
                    'content_type': document.content_type,
                    'created_at': document.created_at.isoformat() if document.created_at else None
                }
            )
            
            if success:
                print("✅ Document processed successfully!")
            else:
                print("❌ Document processing failed")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("🧪 Testing single document processing...")
    print("=" * 50)
    
    test_single_document()
    
    print("=" * 50)
    print("🏁 Test completed")
