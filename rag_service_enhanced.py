#!/usr/bin/env python3
"""
Enhanced RAG service with pgvector support for documents, conversations, and messages
Supports semantic search across entire knowledge base
"""

import json
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime
import openai
from sqlalchemy import text

class EnhancedRAGService:
    def __init__(self, openai_api_key: str, db_session):
        """Initialize the enhanced RAG service"""
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        self.db = db_session
        self.embedding_model = "text-embedding-3-small"
        self.embedding_dimensions = 1536
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using OpenAI"""
        try:
            # Limit text length to prevent API errors
            if len(text) > 8000:
                text = text[:8000]
            
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {str(e)}")
            return None
    
    # ==================== MESSAGE PROCESSING ====================
    
    def process_message(self, message_id: str) -> bool:
        """Process a single message and generate embedding"""
        try:
            from models import Message
            
            message = Message.query.get(message_id)
            if not message:
                print(f"Message {message_id} not found")
                return False
            
            # Check if already processed
            if message.embedding_processed:
                print(f"Message {message_id} already processed")
                return True
            
            print(f"Processing message: {message.id} ({message.role})")
            
            # Generate embedding for message content
            embedding = self.generate_embedding(message.content)
            if not embedding:
                print(f"Failed to generate embedding for message {message_id}")
                return False
            
            # Store embedding
            message.embedding = embedding
            message.embedding_processed = True
            self.db.session.commit()
            
            print(f"✅ Successfully processed message {message_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error processing message {message_id}: {str(e)}")
            self.db.session.rollback()
            return False
    
    def process_conversation_messages(self, conversation_id: str) -> Dict[str, Any]:
        """Process all messages in a conversation"""
        try:
            from models import Message
            
            messages = Message.query.filter_by(conversation_id=conversation_id).all()
            
            processed_count = 0
            error_count = 0
            
            for message in messages:
                if not message.embedding_processed:
                    success = self.process_message(str(message.id))
                    if success:
                        processed_count += 1
                    else:
                        error_count += 1
            
            return {
                'success': True,
                'conversation_id': conversation_id,
                'processed_count': processed_count,
                'error_count': error_count,
                'total_messages': len(messages)
            }
            
        except Exception as e:
            print(f"❌ Error processing conversation messages: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ==================== CONVERSATION PROCESSING ====================
    
    def process_conversation(self, conversation_id: str) -> bool:
        """Process a conversation by creating a summary embedding"""
        try:
            from models import Conversation, Message
            
            conversation = Conversation.query.get(conversation_id)
            if not conversation:
                print(f"Conversation {conversation_id} not found")
                return False
            
            # Check if already processed
            if conversation.embedding_processed:
                print(f"Conversation {conversation_id} already processed")
                return True
            
            print(f"Processing conversation: {conversation.title}")
            
            # Build conversation summary text
            messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.timestamp).all()
            
            if not messages:
                print(f"No messages found in conversation {conversation_id}")
                return False
            
            # Create summary: title + first few exchanges
            summary_parts = [f"Title: {conversation.title}"]
            
            # Add tags if present
            if conversation.tags:
                summary_parts.append(f"Tags: {', '.join(conversation.tags)}")
            
            # Add first 3 message exchanges (up to 6 messages)
            for i, message in enumerate(messages[:6]):
                role_label = "Question" if message.role == "user" else "Answer"
                summary_parts.append(f"{role_label}: {message.content[:500]}")  # Limit each message
            
            summary_text = "\n\n".join(summary_parts)
            
            # Generate embedding
            embedding = self.generate_embedding(summary_text)
            if not embedding:
                print(f"Failed to generate embedding for conversation {conversation_id}")
                return False
            
            # Store embedding
            conversation.embedding = embedding
            conversation.embedding_processed = True
            conversation.embedding_processed_at = datetime.utcnow()
            self.db.session.commit()
            
            print(f"✅ Successfully processed conversation: {conversation.title}")
            return True
            
        except Exception as e:
            print(f"❌ Error processing conversation {conversation_id}: {str(e)}")
            self.db.session.rollback()
            return False
    
    # ==================== SEMANTIC SEARCH ====================
    
    def search_messages(self, query: str, user_id: str = None, 
                       similarity_threshold: float = 0.7, 
                       max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for similar messages using vector similarity"""
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query)
            if not query_embedding:
                return []
            
            # Convert embedding to PostgreSQL vector format
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            # Build SQL query with vector similarity search
            sql = """
                SELECT 
                    m.id,
                    m.conversation_id,
                    m.role,
                    m.content,
                    m.timestamp,
                    c.title as conversation_title,
                    c.user_id,
                    1 - (m.embedding <=> :query_embedding::vector) as similarity
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE m.embedding IS NOT NULL
            """
            
            # Add user filter if provided
            if user_id:
                sql += " AND c.user_id = :user_id"
            
            # Add similarity threshold
            sql += """
                AND 1 - (m.embedding <=> :query_embedding::vector) > :threshold
                ORDER BY m.embedding <=> :query_embedding::vector
                LIMIT :max_results
            """
            
            params = {
                'query_embedding': embedding_str,
                'threshold': similarity_threshold,
                'max_results': max_results
            }
            
            if user_id:
                params['user_id'] = user_id
            
            result = self.db.session.execute(text(sql), params)
            rows = result.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    'id': str(row[0]),
                    'conversation_id': str(row[1]),
                    'role': row[2],
                    'content': row[3],
                    'timestamp': row[4].isoformat() if row[4] else None,
                    'conversation_title': row[5],
                    'similarity_score': float(row[7]),
                    'source_type': 'message'
                })
            
            return results
            
        except Exception as e:
            print(f"Error searching messages: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def search_conversations(self, query: str, user_id: str = None,
                           similarity_threshold: float = 0.7,
                           max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for similar conversations using vector similarity"""
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query)
            if not query_embedding:
                return []
            
            # Convert embedding to PostgreSQL vector format
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            # Build SQL query
            sql = """
                SELECT 
                    id,
                    title,
                    llm_model,
                    created_at,
                    tags,
                    user_id,
                    1 - (embedding <=> :query_embedding::vector) as similarity
                FROM conversations
                WHERE embedding IS NOT NULL
            """
            
            # Add user filter
            if user_id:
                sql += " AND user_id = :user_id"
            
            # Add similarity threshold
            sql += """
                AND 1 - (embedding <=> :query_embedding::vector) > :threshold
                ORDER BY embedding <=> :query_embedding::vector
                LIMIT :max_results
            """
            
            params = {
                'query_embedding': embedding_str,
                'threshold': similarity_threshold,
                'max_results': max_results
            }
            
            if user_id:
                params['user_id'] = user_id
            
            result = self.db.session.execute(text(sql), params)
            rows = result.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    'id': str(row[0]),
                    'title': row[1],
                    'llm_model': row[2],
                    'created_at': row[3].isoformat() if row[3] else None,
                    'tags': row[4] if row[4] else [],
                    'similarity_score': float(row[6]),
                    'source_type': 'conversation'
                })
            
            return results
            
        except Exception as e:
            print(f"Error searching conversations: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def search_all(self, query: str, user_id: str = None,
                  similarity_threshold: float = 0.65,
                  max_results: int = 20) -> Dict[str, List[Dict[str, Any]]]:
        """Search across documents, conversations, and messages"""
        try:
            # Search messages
            messages = self.search_messages(
                query=query,
                user_id=user_id,
                similarity_threshold=similarity_threshold,
                max_results=max_results // 2
            )
            
            # Search conversations
            conversations = self.search_conversations(
                query=query,
                user_id=user_id,
                similarity_threshold=similarity_threshold,
                max_results=max_results // 4
            )
            
            # Search documents (using existing RAG service)
            from rag_service_simple import SimpleRAGService
            import os
            simple_rag = SimpleRAGService(openai_api_key=os.getenv('OPENAI_API_KEY'))
            document_chunks = simple_rag.search_similar_chunks(
                query=query,
                user_id=user_id,
                similarity_threshold=similarity_threshold,
                max_results=max_results // 4
            )
            
            # Add source_type to documents
            for doc in document_chunks:
                doc['source_type'] = 'document'
            
            # Combine and sort by similarity
            all_results = messages + conversations + document_chunks
            all_results.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            return {
                'messages': messages,
                'conversations': conversations,
                'documents': document_chunks,
                'all_results': all_results[:max_results]
            }
            
        except Exception as e:
            print(f"Error in comprehensive search: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'messages': [],
                'conversations': [],
                'documents': [],
                'all_results': []
            }
    
    def get_context_for_query(self, query: str, user_id: str = None,
                             max_context_length: int = 4000) -> str:
        """Get relevant context from all sources for a query"""
        try:
            # Search all sources
            results = self.search_all(
                query=query,
                user_id=user_id,
                similarity_threshold=0.65,
                max_results=15
            )
            
            all_results = results['all_results']
            
            if not all_results:
                return ""
            
            # Build context string
            context_parts = []
            current_length = 0
            
            for result in all_results:
                source_type = result['source_type']
                similarity = result['similarity_score']
                
                if source_type == 'message':
                    # Format message
                    role_label = "Previous Question" if result['role'] == 'user' else "Previous Answer"
                    source_info = f"[{role_label} from '{result['conversation_title']}' (relevance: {similarity:.2f})]"
                    content = result['content']
                    
                elif source_type == 'conversation':
                    # Format conversation reference
                    source_info = f"[Related Conversation: '{result['title']}' (relevance: {similarity:.2f})]"
                    content = f"This conversation may contain relevant information."
                    
                elif source_type == 'document':
                    # Format document chunk
                    source_info = f"[Document: {result['document_name']} (relevance: {similarity:.2f})]"
                    content = result['chunk_text']
                
                else:
                    continue
                
                chunk_text = f"{source_info}\n{content}\n"
                
                if current_length + len(chunk_text) > max_context_length:
                    break
                
                context_parts.append(chunk_text)
                current_length += len(chunk_text)
            
            return "\n".join(context_parts)
            
        except Exception as e:
            print(f"Error getting context for query: {str(e)}")
            return ""
    
    # ==================== BATCH PROCESSING ====================
    
    def process_all_user_data(self, user_id: str) -> Dict[str, Any]:
        """Process all conversations and messages for a user"""
        try:
            from models import Conversation, Message
            
            # Get all user conversations
            conversations = Conversation.query.filter_by(user_id=user_id).all()
            
            total_conversations = len(conversations)
            processed_conversations = 0
            total_messages = 0
            processed_messages = 0
            
            print(f"\n🔄 Processing all data for user {user_id}")
            print(f"Found {total_conversations} conversations")
            
            for i, conv in enumerate(conversations):
                print(f"\n--- Conversation {i+1}/{total_conversations}: {conv.title} ---")
                
                # Process conversation summary
                if not conv.embedding_processed:
                    success = self.process_conversation(str(conv.id))
                    if success:
                        processed_conversations += 1
                
                # Process all messages in conversation
                messages = Message.query.filter_by(conversation_id=conv.id).all()
                total_messages += len(messages)
                
                for message in messages:
                    if not message.embedding_processed:
                        success = self.process_message(str(message.id))
                        if success:
                            processed_messages += 1
            
            print(f"\n✅ Processing complete!")
            print(f"   Conversations: {processed_conversations}/{total_conversations}")
            print(f"   Messages: {processed_messages}/{total_messages}")
            
            return {
                'success': True,
                'user_id': user_id,
                'total_conversations': total_conversations,
                'processed_conversations': processed_conversations,
                'total_messages': total_messages,
                'processed_messages': processed_messages
            }
            
        except Exception as e:
            print(f"❌ Error processing user data: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }

